"""Per-call circuit breaker for provider fetches.

Free data providers (cboe, CFTC, FMP, FRED) intermittently rate-limit or
return malformed responses under load. Without a breaker, every page refresh and
pre-cache cycle keeps hammering a failing endpoint — which both *perpetuates*
the rate-limit and lets confusing provider-side errors crash through on repeat
(e.g. cboe's CDN returning a JSON throttle page that OpenBB then tries to read
as CSV bytes).

`guarded` wraps a fetch so that after a few consecutive failures the call
"opens": further calls fail fast with a clean `CircuitOpen` (no provider hit)
until a cooldown elapses, then one trial is allowed (half-open); success closes
it. Breakers are keyed per (function, args), so one dead symbol (e.g. the
unavailable GC futures curve) never suppresses a healthy one (e.g. VIX).

Sits *under* `@cached`: a warm cache never reaches the breaker; only live
provider calls on a cache miss are guarded.
"""

from __future__ import annotations

import functools
import threading
import time
from collections.abc import Callable
from typing import TypeVar

R = TypeVar("R")

DEFAULT_FAIL_THRESHOLD = 3
DEFAULT_COOLDOWN_S = 300  # 5 minutes


class CircuitOpen(RuntimeError):
    """Raised instead of calling a provider while its circuit is open."""


class _Breaker:
    __slots__ = ("name", "fail_threshold", "cooldown_s", "_failures", "_opened_at", "_lock")

    def __init__(self, name: str, fail_threshold: int, cooldown_s: float) -> None:
        self.name = name
        self.fail_threshold = fail_threshold
        self.cooldown_s = cooldown_s
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    def check(self) -> None:
        """Raise CircuitOpen if the circuit is open and still cooling down."""
        with self._lock:
            if self._opened_at is None:
                return
            remaining = self.cooldown_s - (time.monotonic() - self._opened_at)
            if remaining > 0:
                raise CircuitOpen(
                    f"{self.name}: provider skipped after {self._failures} "
                    f"consecutive failures; retry in {int(remaining) + 1}s"
                )
            # Cooldown elapsed → fall through to allow one trial (half-open).

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.fail_threshold:
                self._opened_at = time.monotonic()  # (re)open / extend cooldown


_breakers: dict[str, _Breaker] = {}
_breakers_lock = threading.Lock()


def _breaker(name: str, fail_threshold: int, cooldown_s: float) -> _Breaker:
    with _breakers_lock:
        breaker = _breakers.get(name)
        if breaker is None:
            breaker = _Breaker(name, fail_threshold, cooldown_s)
            _breakers[name] = breaker
        return breaker


def guarded(
    fail_threshold: int = DEFAULT_FAIL_THRESHOLD,
    cooldown_s: float = DEFAULT_COOLDOWN_S,
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """Wrap a provider fetch with a per-(function, args) circuit breaker."""

    def decorator(fn: Callable[..., R]) -> Callable[..., R]:
        base = fn.__qualname__

        @functools.wraps(fn)
        def wrapper(*args: object, **kwargs: object) -> R:
            key = f"{base}:{args!r}:{tuple(sorted(kwargs.items()))!r}"
            breaker = _breaker(key, fail_threshold, cooldown_s)
            breaker.check()
            try:
                result = fn(*args, **kwargs)
            except Exception:
                breaker.record_failure()
                raise
            breaker.record_success()
            return result

        return wrapper

    return decorator


def reset() -> None:
    """Clear all breakers (test/diagnostic helper)."""
    with _breakers_lock:
        _breakers.clear()
