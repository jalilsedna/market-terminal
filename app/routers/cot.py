"""V4 — COT / Positioning router (SPEC.md §4 V4).

Weekly CFTC Commitment of Traders for the watchlist contracts. Value-add over
OpenBB's raw endpoint: it computes net positioning, weekly change, multi-week
trend, and 1y/3y extremes, and maps the user's instruments to CFTC codes —
not a 1:1 passthrough.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import Envelope
from services import cot

_COT_FRESHNESS = "weekly (CFTC COT, ~3-day lag) — research context, not a signal"

router = APIRouter(prefix="/cot", tags=["V4 — COT / Positioning"])


@router.get("/search", response_model=Envelope)
def cot_search(query: str = Query(..., description="Contract name to search, e.g. 'gold'")) -> Envelope:
    """Look up CFTC contract codes by name (to verify/correct the symbol map)."""
    return Envelope(data=cot.search(query), provider="cftc", freshness="reference")


@router.get("/dashboard", response_model=Envelope)
def cot_dashboard() -> Envelope:
    """COT positioning summary across the full watchlist (each contract fault-tolerant)."""
    return Envelope(data=cot.dashboard(), provider="cftc", freshness=_COT_FRESHNESS)


@router.get("/positioning", response_model=Envelope)
def cot_positioning(
    instrument: str | None = Query(None, description="Watchlist shorthand, e.g. 'GC', '6E'"),
    code: str | None = Query(None, description="Raw CFTC contract market code, e.g. '088691'"),
) -> Envelope:
    """COT positioning summary for one contract, by instrument shorthand or raw code."""
    try:
        data = cot.positioning(instrument=instrument, code=code)
    except ValueError as exc:  # bad/missing input → client error
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — provider failure → degraded envelope
        return Envelope(ok=False, provider="cftc", freshness=_COT_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="cftc", freshness=_COT_FRESHNESS)
