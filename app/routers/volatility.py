"""Volatility router (ROADMAP E3) — realized vol, regime, short-horizon forecast.

The forecasting pillar (pivoted from price to volatility — see docs/decisions.md
§E). Research context for sizing/regime awareness, never a trade trigger.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import Envelope
from services import volatility as vol_svc

router = APIRouter(prefix="/volatility", tags=["Volatility"])

_FRESHNESS = "EOD realized vol + short-horizon forecast — research context, not a signal"


@router.get("", response_model=Envelope)
def dashboard(horizon: int = Query(5, ge=1, le=21, description="Forecast horizon in days")) -> Envelope:
    """Volatility + regime read across the whole watchlist."""
    return Envelope(data=vol_svc.dashboard(horizon), provider="derived (fmp)", freshness=_FRESHNESS)


@router.get("/{instrument}", response_model=Envelope)
def one(
    instrument: str,
    horizon: int = Query(5, ge=1, le=21, description="Forecast horizon in days"),
) -> Envelope:
    """Realized vol, regime (calm/normal/elevated/stressed vs ~3y), and a
    short-horizon vol forecast for one watchlist instrument (e.g. 'GC')."""
    try:
        data = vol_svc.volatility(instrument, horizon)
    except ValueError as exc:  # unknown instrument
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Envelope(data=data, provider="derived (fmp)", freshness=_FRESHNESS)
