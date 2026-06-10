"""Unified instrument registry — add/remove/list/search tracked assets."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.schemas import Envelope
from config import get_settings
from services import instruments as reg

router = APIRouter(prefix="/instruments", tags=["Instruments"])

_FRESHNESS = "EOD — research context, not a trade signal"


class AddInstrument(BaseModel):
    asset: str = Field(description="futures | crypto | forex | equity | etf")
    symbol: str
    label: str | None = None
    meta: dict | None = None


@router.get("", response_model=Envelope)
def list_instruments() -> Envelope:
    """All tracked instruments with capability flags (no live prices)."""
    items = [i.to_dict() for i in reg.list_all()]
    return Envelope(
        data={"instruments": items, "count": len(items)},
        provider="registry",
        freshness=_FRESHNESS,
    )


@router.get("/dashboard", response_model=Envelope)
def instruments_dashboard() -> Envelope:
    """Full dashboard: prices, changes, vol/regime per instrument."""
    from services import watchlist as wl

    return Envelope(data=wl.watchlist(), provider="yfinance", freshness=_FRESHNESS)


@router.post("", response_model=Envelope)
def add_instrument(req: AddInstrument) -> Envelope:
    try:
        inst = reg.add(req.asset, req.symbol, req.label, req.meta)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Envelope(data=inst.to_dict(), provider="registry", freshness=_FRESHNESS)


@router.delete("/{item_id:path}", response_model=Envelope)
def remove_instrument(item_id: str) -> Envelope:
    reg.remove(item_id)
    items = [i.to_dict() for i in reg.list_all()]
    return Envelope(
        data={"instruments": items, "count": len(items)},
        provider="registry",
        freshness=_FRESHNESS,
    )


@router.get("/search", response_model=Envelope)
def search_instruments(
    query: str = Query("", min_length=0),
    source: str = Query("alpaca", description="alpaca — tradable US equities (read-only)"),
    limit: int = Query(30, ge=1, le=100),
) -> Envelope:
    """Discover symbols to add (Alpaca tradable catalog when configured)."""
    if source != "alpaca":
        raise HTTPException(status_code=400, detail=f"unknown source {source!r}")
    if not get_settings().alpaca_enabled:
        return Envelope(
            ok=False,
            data={"results": []},
            error="Alpaca not configured — set ALPACA_API_KEY and ALPACA_API_SECRET",
            freshness=_FRESHNESS,
        )
    from obb_layer import alpaca

    try:
        results = alpaca.list_assets(search=query or None, limit=limit)
    except alpaca.AlpacaDisabled as exc:
        return Envelope(ok=False, data={"results": []}, error=str(exc), freshness=_FRESHNESS)
    except alpaca.AlpacaError as exc:
        return Envelope(ok=False, data={"results": []}, error=str(exc), freshness=_FRESHNESS)
    return Envelope(data={"results": results, "query": query}, provider="alpaca", freshness=_FRESHNESS)
