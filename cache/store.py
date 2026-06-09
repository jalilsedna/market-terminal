"""In-process TTL cache (SPEC.md §6).

A small, thread-safe, in-memory cache keyed by (namespace, params) with the
per-data-type TTLs declared in `cache/__init__.py`. Mandatory infra, not an
optimization: free providers throttle, so every `obb_layer/` data function
routes its provider calls through here.

Scope deliberately minimal for a single-user local terminal: the cache lives in
the process and resets on restart. It can be swapped for a disk/SQLite backend
later (Phase 3 pre-cache jobs) without touching call sites — they only use
`cached()` / `get_or_set()`.
"""

from __future__ import annotations

import functools
import hashlib
import json
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

from cache import TTL_SECONDS

T = TypeVar("T")

# key -> (expires_at_epoch, value)
_store: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()


def _key(namespace: str, payload: Any) -> str:
    """Stable cache key from a namespace + JSON-able call signature."""
    blob = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]
    return f"{namespace}:{digest}"


def get_or_set(category: str, namespace: str, payload: Any, producer: Callable[[], T]) -> T:
    """Return a cached value or compute, store, and return it.

    `category` selects the TTL from `TTL_SECONDS` (e.g. "eod", "cot", "macro").
    The `producer` runs OUTSIDE the lock so a slow provider call never blocks
    other cache reads.
    """
    ttl = TTL_SECONDS.get(category, 0)
    key = _key(namespace, payload)
    now = time.monotonic()

    with _lock:
        hit = _store.get(key)
        if hit and hit[0] > now:
            return hit[1]

    value = producer()

    with _lock:
        _store[key] = (now + ttl, value)
    return value


def cached(category: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator caching a function's result by its (kw)args under `category`.

    Args must be JSON-serialisable (they are here — symbols, dates, providers).
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        namespace = f"{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            payload = {"args": args, "kwargs": kwargs}
            return get_or_set(category, namespace, payload, lambda: func(*args, **kwargs))

        return wrapper

    return decorator


def clear() -> None:
    """Drop all cached entries (test/diagnostic helper)."""
    with _lock:
        _store.clear()


def stats() -> dict:
    """Cache introspection for /doctor: total vs live (non-expired) entries and
    the distinct namespaces (cached functions) currently populated."""
    now = time.monotonic()
    with _lock:
        items = list(_store.items())
    live = sum(1 for _k, (expires, _v) in items if expires > now)
    namespaces = sorted({k.rsplit(":", 1)[0] for k, _ in items})
    return {"entries": len(items), "live": live, "namespaces": namespaces}
