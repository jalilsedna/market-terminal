"""V5 — Futures Term Structure router (SPEC.md §4 V5).

Contango/backwardation for GC + energy curves. Value-add over OpenBB's raw
curve endpoint: it classifies the structure and computes the front/back spread.

Note: the VIX term structure (SPEC's fear gauge) needs the `cboe` provider,
which is not installed in the current environment. Adding `openbb-cboe` to
requirements would enable it.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import Envelope
from services import term_structure

router = APIRouter(prefix="/term-structure", tags=["V5 — Term Structure"])

_FRESHNESS = "EOD forward curve — research context, not a tradeable signal"


@router.get("", response_model=Envelope)
def term_structure_all() -> Envelope:
    """Term structure across all tracked curves (GC + energy), each fault-tolerant."""
    return Envelope(data=term_structure.dashboard(), provider="yfinance", freshness=_FRESHNESS)


@router.get("/{code}", response_model=Envelope)
def term_structure_one(code: str) -> Envelope:
    """Term structure for one curve root (e.g. 'GC', 'CL', 'NG')."""
    try:
        data = term_structure.curve(code)
    except ValueError as exc:  # unknown curve → client error
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — provider failure → degraded envelope
        return Envelope(ok=False, provider="yfinance", freshness=_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="yfinance", freshness=_FRESHNESS)
