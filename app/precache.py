"""Scheduled pre-cache warmer (Phase 3 — SPEC.md §5 step 12).

Periodically calls each view's top-level service function so the underlying
obb_layer fetches populate the in-process TTL cache. The result: views serve
from a warm cache instead of blocking on a provider round-trip during a session.

Runs in a daemon thread started from the app lifespan, *after* OpenBB has been
warmed on the main thread (so the one-time static-package rebuild has already
happened — see app/main.py). Each warmer is fault-tolerant: a provider failure
is logged and the cycle continues.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from services import cot, macro, news, screener, term_structure, watchlist

logger = logging.getLogger("precache")
# Make our INFO lines visible in the uvicorn console: uvicorn only configures its
# own loggers, and the root logger defaults to WARNING, so without this the
# "started"/"warmed" messages would be swallowed. Self-contained handler.
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

# (label, warmer) — calling each populates the caches its view depends on.
WARMERS: list[tuple[str, Callable[[], object]]] = [
    ("macro", macro.build_dashboard),
    ("watchlist", watchlist.watchlist),
    ("cot", cot.dashboard),
    ("term_structure", term_structure.dashboard),
    ("sectors", screener.sector_rotation),
    ("news", lambda: news.feed(limit=40)),
]


def warm_all() -> None:
    """Run one warming cycle over every view (fault-tolerant)."""
    started = time.monotonic()
    ok = 0
    for label, fn in WARMERS:
        try:
            fn()
            ok += 1
        except Exception as exc:  # noqa: BLE001 — never let one view stop the cycle
            logger.warning("precache: %s failed: %s", label, exc)
    logger.info("precache: warmed %d/%d views in %.1fs", ok, len(WARMERS), time.monotonic() - started)


def start(interval_min: int) -> Callable[[], None]:
    """Start the background warming loop; returns a stop() callback.

    interval_min <= 0 disables the scheduler (returns a no-op stop()).
    """
    if interval_min <= 0:
        logger.info("precache: disabled (interval_min=%d)", interval_min)
        return lambda: None

    stop_event = threading.Event()
    interval_s = interval_min * 60

    def _loop() -> None:
        warm_all()  # warm immediately on startup
        while not stop_event.wait(interval_s):
            warm_all()

    thread = threading.Thread(target=_loop, name="precache", daemon=True)
    thread.start()
    logger.info("precache: started, every %d min", interval_min)

    def stop() -> None:
        stop_event.set()

    return stop
