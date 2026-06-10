"""Legacy /custom routes — alias the unified instrument registry (C6 compat)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.routers import instruments as inst_router
from app.schemas import Envelope
from services import watchlist as wl

router = APIRouter(prefix="/custom", tags=["Custom Watchlist (legacy)"])

_FRESHNESS = "EOD prices + realized-vol read — research context, not a signal"
_PROVIDER = "fmp"


class AddInstrument(BaseModel):
    asset: str
    symbol: str
    label: str | None = None


@router.get("", response_model=Envelope)
def get_custom() -> Envelope:
    data = wl.watchlist()
    return Envelope(data=data, provider=_PROVIDER, freshness=_FRESHNESS)


@router.post("", response_model=Envelope)
def add_custom(req: AddInstrument) -> Envelope:
    body = inst_router.AddInstrument(asset=req.asset, symbol=req.symbol, label=req.label)
    try:
        return inst_router.add_instrument(body)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{item_id:path}", response_model=Envelope)
def remove_custom(item_id: str) -> Envelope:
    return inst_router.remove_instrument(item_id)
