"""OpenBB data functions for V1 — Macro Dashboard (SPEC.md §4 V1).

Thin wrappers over OpenBB: fetch → normalize to plain record-dicts → cache.
FX and index history use the EOD provider chain (FMP first). FRED / Fed paths
unchanged.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from cache.store import cached
from circuit import guarded
from obb_layer.client import get_obb
from obb_layer.normalize import to_records
from obb_layer.providers import eod_with_fallback

# Liquid ETF fallbacks when a cash-index ticker is thin or returns bad bars on FMP.
_INDEX_ETF_FALLBACK: dict[str, str] = {
    "^GSPC": "SPY",
    "^NDX": "QQQ",
    "^DJI": "DIA",
}


def _usable_index_bars(rows: list[dict], *, min_bars: int = 6) -> bool:
    """Enough finite daily closes to compute 1w % change."""
    if len(rows) < min_bars:
        return False
    closes = 0
    for row in rows:
        try:
            if math.isfinite(float(row.get("close"))):
                closes += 1
        except (TypeError, ValueError):
            continue
    return closes >= min_bars


@cached("eod")
@guarded()
def fx_history(pair: str) -> list[dict]:
    """Daily OHLCV for a spot FX pair (e.g. 'EURUSD')."""
    return eod_with_fallback(
        get_obb().currency.price.historical, pair, asset="forex",
    )


@cached("eod")
@guarded()
def index_history(symbol: str) -> list[dict]:
    """Daily OHLCV for a cash index (e.g. '^GSPC', '^NDX', '^DJI').

    FMP REST first (reliable for regime/macro reads), then a liquid ETF proxy
    when the index ticker is thin, then the OpenBB index EOD chain as last resort.
    """
    from obb_layer import fmp_market

    sym = symbol.upper().strip()
    candidates = [sym]
    if sym in _INDEX_ETF_FALLBACK:
        candidates.append(_INDEX_ETF_FALLBACK[sym])

    for candidate in candidates:
        try:
            rows = fmp_market.history(candidate)
            if _usable_index_bars(rows):
                return rows
        except Exception:  # noqa: BLE001 — try next candidate / chain
            continue

    return eod_with_fallback(get_obb().index.price.historical, sym)


@cached("macro")
@guarded()
def fred_series(series_id: str) -> list[dict]:
    """A FRED economic series (e.g. 'DGS10', 'UNRATE'). Provider: fred."""
    obb = get_obb()
    return to_records(obb.economy.fred_series(symbol=series_id, provider="fred"))


@cached("macro")
@guarded()
def yield_curve() -> list[dict]:
    """Latest US Treasury yield curve (maturity, rate). Provider: federal_reserve."""
    obb = get_obb()
    return to_records(obb.fixedincome.government.yield_curve(provider="federal_reserve"))


@guarded()
def economic_calendar(days_ahead: int = 7) -> list[dict]:
    """Upcoming economic calendar for the next `days_ahead` days (FMP only)."""
    obb = get_obb()
    today = date.today()
    obbject = obb.economy.calendar(
        provider="fmp",
        start_date=today.isoformat(),
        end_date=(today + timedelta(days=days_ahead)).isoformat(),
    )
    return to_records(obbject)
