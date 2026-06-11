"""Smart Money / Ownership router (ROADMAP H3 — equity subset).

`GET /ownership/{ticker}` — interpreted insider + congressional trading read.
Auth-gated like every view. Research context, never a trade trigger.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import Envelope
from config import get_settings
from services import ownership

router = APIRouter(prefix="/ownership", tags=["Smart Money / Ownership"])

_FRESHNESS = "disclosed insider + congressional trades (FMP) — research context, not a signal"


@router.get("/{ticker}", response_model=Envelope)
def ownership_view(ticker: str) -> Envelope:
    """Insider buy/sell read + recent insider and congressional transactions."""
    if not get_settings().fmp_enabled:
        return Envelope(ok=False, provider="fmp", freshness=_FRESHNESS,
                        error="Ownership needs an FMP key — set FMP_API_KEY.")
    try:
        data = ownership.ownership(ticker)
    except Exception as exc:  # noqa: BLE001 — degrade rather than 500
        return Envelope(ok=False, provider="fmp", freshness=_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="fmp", freshness=_FRESHNESS)
