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
from obb_layer.providers import eod_with_fallback


@cached("eod")
@guarded()
def etf_history(symbol: str) -> list[dict]:
    """Daily OHLCV for a sector ETF (e.g. 'XLK'). Tries the EOD provider chain
    (B4) so a yfinance throttle on the 11-ETF fan-out falls back instead of
    dropping sectors."""
    return eod_with_fallback(get_obb().etf.historical, symbol)


@cached("eod")
@guarded()
def screen(**criteria: Any) -> list[dict]:
    """Run the yfinance equity screener with the given filter criteria."""
    obb = get_obb()
    clean = {k: v for k, v in criteria.items() if v is not None}
    return to_records(obb.equity.screener(provider="yfinance", **clean), sort_by_date=False)
