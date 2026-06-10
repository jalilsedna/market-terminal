"""V5 — Futures Term Structure router (SPEC.md §4 V5).

Contango/backwardation for GC + energy curves (FMP), plus the VIX fear gauge (cboe).
Value-add over raw curve data: classifies structure, computes front/back spread,
and reads the VIX curve as risk-on/off.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import Envelope
from config import get_settings
from services import term_structure

router = APIRouter(prefix="/term-structure", tags=["V5 — Term Structure"])

_FRESHNESS = "EOD forward curve — research context, not a tradeable signal"
_PROVIDER = "fmp + cboe (VIX)"


def _provider_label() -> str:
    if get_settings().fmp_enabled:
        return _PROVIDER
    return "cboe (VIX only — set FMP_API_KEY for GC/CL/NG)"


@router.get("", response_model=Envelope)
def term_structure_all() -> Envelope:
    """Term structure across all tracked curves (GC + energy), each fault-tolerant."""
    return Envelope(data=term_structure.dashboard(), provider=_provider_label(), freshness=_FRESHNESS)


@router.get("/{code}", response_model=Envelope)
def term_structure_one(code: str) -> Envelope:
    """Term structure for one curve root (e.g. 'GC', 'CL', 'NG', 'VIX')."""
    try:
        data = term_structure.curve(code)
    except ValueError as exc:  # unknown curve → client error
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — provider failure → degraded envelope
        return Envelope(ok=False, provider=_provider_label(), freshness=_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider=_provider_label(), freshness=_FRESHNESS)
