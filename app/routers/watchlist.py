"""Instruments dashboard router (legacy /watchlist path).

Returns live EOD metrics for every instrument in the unified registry.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import Envelope
from services import watchlist as wl

router = APIRouter(prefix="/watchlist", tags=["Instruments"])

_FRESHNESS = "EOD (daily) — research context, not a tradeable signal"


@router.get("", response_model=Envelope)
def watchlist_all() -> Envelope:
    """All tracked instruments with live metrics (fault-tolerant per row)."""
    return Envelope(data=wl.watchlist(), provider="fmp", freshness=_FRESHNESS)


@router.get("/{ref:path}", response_model=Envelope)
def watchlist_one(ref: str) -> Envelope:
    """One instrument by id, code, or symbol."""
    try:
        data = wl.instrument_summary(ref)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        return Envelope(ok=False, provider="fmp", freshness=_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="fmp", freshness=_FRESHNESS)
