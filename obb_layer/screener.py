"""OpenBB data functions for V6 — Screener / Sector Rotation (SPEC.md §4 V6).

Thin fetch→normalize→cache wrappers. The spec's `equity.compare.groups` heatmap
isn't available in this OpenBB version, so sector rotation is built from the 11
SPDR sector ETFs via free yfinance ETF history; the screener uses the free
yfinance equity screener.
"""

from __future__ import annotations

from typing import Any

from cache.store import cached
from circuit import guarded
from obb_layer.client import get_obb
from obb_layer.normalize import to_records


@cached("eod")
@guarded()
def etf_history(symbol: str) -> list[dict]:
    """Daily OHLCV for an ETF (e.g. 'XLK'). Provider: yfinance."""
    obb = get_obb()
    return to_records(obb.etf.historical(symbol=symbol, provider="yfinance"))


@cached("eod")
@guarded()
def screen(**criteria: Any) -> list[dict]:
    """Run the yfinance equity screener with the given filter criteria."""
    obb = get_obb()
    clean = {k: v for k, v in criteria.items() if v is not None}
    return to_records(obb.equity.screener(provider="yfinance", **clean), sort_by_date=False)
