"""SEC filings router (ROADMAP H4 — filings subset).

`GET /filings/{ticker}` — recent SEC filings with event flags. Auth-gated.
Research context, never a trade trigger.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import Envelope
from config import get_settings
from services import filings

router = APIRouter(prefix="/filings", tags=["SEC Filings"])

_FRESHNESS = "recent SEC filings (FMP) — research context, not a signal"


@router.get("/{ticker}", response_model=Envelope)
def filings_view(ticker: str, limit: int = Query(15, ge=1, le=50)) -> Envelope:
    """Recent SEC filings (8-K / 10-Q / 10-K / 4 / …) with event flags + links."""
    if not get_settings().fmp_enabled:
        return Envelope(ok=False, provider="fmp", freshness=_FRESHNESS,
                        error="Filings need an FMP key — set FMP_API_KEY.")
    try:
        data = filings.filings(ticker, limit=limit)
    except Exception as exc:  # noqa: BLE001 — degrade rather than 500
        return Envelope(ok=False, provider="fmp", freshness=_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="fmp", freshness=_FRESHNESS)
