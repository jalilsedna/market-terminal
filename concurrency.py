"""Small concurrency helper for fan-out provider calls.

The views aggregate many independent, network-bound provider calls (per
instrument, per sector ETF, per news ticker). Running them sequentially is slow
(yfinance is several seconds per call); since they're I/O-bound, a thread pool
overlaps the waits. Workers are capped to stay friendly to provider rate limits.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")
R = TypeVar("R")

MAX_WORKERS = 6


def parallel_map(fn: Callable[[T], R], items: Iterable[T], workers: int = MAX_WORKERS) -> list[R]:
    """Map `fn` over `items` concurrently, preserving input order.

    `fn` should handle its own errors (return a value rather than raise) so one
    failed item doesn't abort the batch — callers here build fault-tolerant
    per-item workers.
    """
    items = list(items)
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as pool:
        return list(pool.map(fn, items))
