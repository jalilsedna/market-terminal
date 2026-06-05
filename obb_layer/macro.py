"""OpenBB data functions for V1 — Macro Dashboard (SPEC.md §4 V1).

Thin wrappers over OpenBB: fetch → normalize to plain record-dicts → cache.
All endpoints/params here were confirmed against live OpenBB 4.4.1 by the
Phase-0 probe (`obb_layer/probe.py`). No domain logic lives here — derived
metrics (% change, 2s10s, latest tiles) are computed in `services/macro.py`.

Per CLAUDE.md, this module is part of the only layer that touches OpenBB.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from cache.store import cached
from obb_layer.client import get_obb


def _records(obbject: Any) -> list[dict]:
    """Normalize an OBBject to a list of plain dicts, sorted oldest→newest."""
    rows: list[dict]
    try:
        df = obbject.to_dataframe().reset_index()
        rows = df.to_dict("records")
    except Exception:  # noqa: BLE001 — fall back to raw results
        results = getattr(obbject, "results", None) or []
        rows = [r.model_dump() if hasattr(r, "model_dump") else dict(r) for r in results]
    # Sort by any date-like column so callers can rely on ordering.
    for key in ("date", "Date", "datetime"):
        if rows and key in rows[0]:
            rows.sort(key=lambda r: str(r.get(key)))
            break
    return rows


@cached("eod")
def fx_history(pair: str) -> list[dict]:
    """Daily OHLCV for a spot FX pair (e.g. 'EURUSD'). Provider: yfinance."""
    obb = get_obb()
    return _records(obb.currency.price.historical(symbol=pair, provider="yfinance"))


@cached("eod")
def index_history(symbol: str) -> list[dict]:
    """Daily OHLCV for a cash index (e.g. '^NDX', '^DJI'). Provider: yfinance."""
    obb = get_obb()
    return _records(obb.index.price.historical(symbol=symbol, provider="yfinance"))


@cached("macro")
def fred_series(series_id: str) -> list[dict]:
    """A FRED economic series (e.g. 'DGS10', 'UNRATE'). Provider: fred."""
    obb = get_obb()
    return _records(obb.economy.fred_series(symbol=series_id, provider="fred"))


@cached("macro")
def yield_curve() -> list[dict]:
    """Latest US Treasury yield curve (maturity, rate). Provider: federal_reserve."""
    obb = get_obb()
    return _records(obb.fixedincome.government.yield_curve(provider="federal_reserve"))


def economic_calendar(days_ahead: int = 7) -> list[dict]:
    """Upcoming economic calendar for the next `days_ahead` days.

    Deliberately uses ONLY the FMP provider: the Phase-0 probe showed FRED's
    calendar times out and TradingEconomics is paid. With a free FMP key this
    fails fast with a 402 (paid endpoint); the caller treats that as a degraded
    panel rather than a hard error. Not cached — it either fails fast or returns
    a small, time-sensitive window.
    """
    obb = get_obb()
    today = date.today()
    obbject = obb.economy.calendar(
        provider="fmp",
        start_date=today.isoformat(),
        end_date=(today + timedelta(days=days_ahead)).isoformat(),
    )
    return _records(obbject)
