"""OpenBB data functions for V1 — Macro Dashboard (SPEC.md §4 V1).

Thin wrappers over OpenBB: fetch → normalize to plain record-dicts → cache.
FX and index history use the EOD provider chain (FMP first). FRED / Fed paths
unchanged.
"""

from __future__ import annotations

from datetime import date, timedelta

from cache.store import cached
from circuit import guarded
from obb_layer.client import get_obb
from obb_layer.normalize import to_records
from obb_layer.providers import eod_with_fallback


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
    """Daily OHLCV for a cash index (e.g. '^NDX', '^DJI')."""
    return eod_with_fallback(get_obb().index.price.historical, symbol)


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
