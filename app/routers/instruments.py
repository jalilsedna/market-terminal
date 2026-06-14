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

    return Envelope(data=wl.watchlist(), provider="fmp", freshness=_FRESHNESS)


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


@router.post("/ensure-book", response_model=Envelope)
def ensure_default_book() -> Envelope:
    """Ensure the canonical default book (reference futures + spot forex/metals,
    the IBKR execution universe) is tracked. ADD-only and idempotent — never
    removes anything, so it's safe to run against a populated registry to
    guarantee forex+metals research exists before an IBKR session (ROADMAP A10).
    """
    result = reg.ensure_default_book()
    items = [i.to_dict() for i in reg.list_all()]
    return Envelope(
        data={**result, "instruments": items, "count": len(items)},
        provider="registry",
        freshness=_FRESHNESS,
    )


class PruneInstruments(BaseModel):
    refs: list[str] = Field(description="instrument ids / codes / symbols to remove")


@router.post("/prune", response_model=Envelope)
def prune_instruments(req: PruneInstruments) -> Envelope:
    """Bulk-remove named instruments (clear transient/junk tickers in one call).
    Only removes what's listed — never a blanket wipe."""
    result = reg.prune(req.refs)
    items = [i.to_dict() for i in reg.list_all()]
    return Envelope(
        data={**result, "instruments": items, "count": len(items)},
        provider="registry",
        freshness=_FRESHNESS,
    )


@router.get("/search", response_model=Envelope)
def search_instruments(
    query: str = Query("", min_length=0),
    asset: str = Query("equity", description="futures | crypto | forex | equity | etf"),
    limit: int = Query(25, ge=1, le=100),
) -> Envelope:
    """Autocomplete symbols for the Registry — filters as you type."""
    from services import custom_store, symbol_search

    asset = asset.lower().strip()
    if asset not in custom_store.VALID_ASSETS:
        raise HTTPException(status_code=400, detail=f"unknown asset {asset!r}")

    results = symbol_search.search(asset, query, limit=limit)
    if asset in ("equity", "etf"):
        provider = "alpaca+catalog" if get_settings().alpaca_enabled else "catalog"
        note = None if get_settings().alpaca_enabled else (
            "Alpaca not configured — showing curated symbols; set ALPACA_API_KEY for full US universe"
        )
    else:
        provider = "catalog"
        note = None
    return Envelope(
        data={"results": results, "query": query, "asset": asset, "note": note},
        provider=provider,
        freshness=_FRESHNESS,
    )
