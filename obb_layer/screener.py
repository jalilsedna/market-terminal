"""OpenBB data functions for V6 — Screener / Sector Rotation (SPEC.md §4 V6).

Sector rotation is built from the 11 SPDR sector ETFs via the EOD provider chain
(FMP first). The equity screener uses OpenBB's FMP provider.
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
    """Daily OHLCV for a sector ETF (e.g. 'XLK'). Tries the EOD provider chain."""
    return eod_with_fallback(get_obb().etf.historical, symbol)


@cached("eod")
@guarded()
def screen(**criteria: Any) -> list[dict]:
    """Run the FMP equity screener with the given filter criteria."""
    obb = get_obb()
    clean = {k: v for k, v in criteria.items() if v is not None}
    return to_records(obb.equity.screener(provider="fmp", **clean), sort_by_date=False)
