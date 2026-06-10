"""Chart router — TradingView quick-picks from the instrument registry."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import Envelope
from services import instruments as reg

router = APIRouter(prefix="/chart", tags=["Chart"])

_FRESHNESS = "TradingView chart (display data) — research only, not a trade trigger"


@router.get("/symbols", response_model=Envelope)
def chart_symbols() -> Envelope:
    """Tracked instruments that have a TradingView symbol in metadata."""
    picks = []
    for inst in reg.list_all():
        tv = inst.meta.get("tv_symbol")
        if not tv:
            continue
        picks.append({
            "code": inst.code or inst.id,
            "name": inst.label,
            "tv_symbol": tv,
            "id": inst.id,
        })
    return Envelope(data={"picks": picks}, provider="tradingview", freshness=_FRESHNESS)
