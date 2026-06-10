"""V5 — Futures Term Structure router (SPEC.md §4 V5).

The VIX fear gauge (cboe) is the real term structure on the current stack;
GC/CL/NG are marked unavailable (no live per-expiry futures source) and degrade
to a clean note. Value-add: classifies structure, computes front/back spread,
and reads the VIX curve as risk-on/off.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import Envelope
from services import term_structure

router = APIRouter(prefix="/term-structure", tags=["V5 — Term Structure"])

_FRESHNESS = "EOD forward curve — research context, not a tradeable signal"
_PROVIDER = "cboe (VIX); commodity curves need a futures data plan"


@router.get("", response_model=Envelope)
def term_structure_all() -> Envelope:
    """Term structure across tracked curves; GC/CL/NG render an unavailable note."""
    return Envelope(data=term_structure.dashboard(), provider=_PROVIDER, freshness=_FRESHNESS)


@router.get("/{code}", response_model=Envelope)
def term_structure_one(code: str) -> Envelope:
    """Term structure for one curve root (e.g. 'GC', 'CL', 'NG', 'VIX')."""
    try:
        data = term_structure.curve(code)
    except term_structure.CurveUnavailable as exc:  # no data source → clean note
        return Envelope(ok=False, provider=_PROVIDER, freshness=_FRESHNESS, error=str(exc))
    except ValueError as exc:  # unknown curve → client error
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — provider failure → degraded envelope
        return Envelope(ok=False, provider=_PROVIDER, freshness=_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider=_PROVIDER, freshness=_FRESHNESS)
