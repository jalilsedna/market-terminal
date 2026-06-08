"""Custom multi-asset watchlist router (ROADMAP C6).

Add/remove arbitrary instruments (futures, crypto, forex, equity, ETF); each
shows EOD price + change + a volatility/regime read. Research context only.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas import Envelope
from services import custom_store
from services import custom_watchlist as cw

router = APIRouter(prefix="/custom", tags=["Custom Watchlist"])

_FRESHNESS = "EOD prices + realized-vol read — research context, not a signal"
_PROVIDER = "derived (yfinance)"


class AddInstrument(BaseModel):
    asset: str  # futures | crypto | forex | equity | etf
    symbol: str
    label: str | None = None


@router.get("", response_model=Envelope)
def get_custom() -> Envelope:
    """The custom watchlist with live price + vol/regime per instrument."""
    return Envelope(data=cw.dashboard(), provider=_PROVIDER, freshness=_FRESHNESS)


@router.post("", response_model=Envelope)
def add_custom(req: AddInstrument) -> Envelope:
    """Add an instrument, then return the refreshed list."""
    try:
        custom_store.add(req.asset, req.symbol, req.label)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Envelope(data=cw.dashboard(), provider=_PROVIDER, freshness=_FRESHNESS)


@router.delete("/{item_id:path}", response_model=Envelope)
def remove_custom(item_id: str) -> Envelope:
    """Remove an instrument by id ('asset:symbol'), then return the refreshed list."""
    custom_store.remove(item_id)
    return Envelope(data=cw.dashboard(), provider=_PROVIDER, freshness=_FRESHNESS)
