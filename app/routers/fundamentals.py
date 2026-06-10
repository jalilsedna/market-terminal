"""Fundamentals router (ROADMAP H, Phase 1).

`GET /fundamentals/{ticker}` — the per-ticker fundamentals dashboard (profile,
valuation, quality, growth, peers, segmentation) from FMP. Auth-gated like every
view. NOTE: no MCP tool here yet — per the plan, the terminal brain is built out
fully before any FMP-derived data is exposed to Alice (that's the final phase).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import Envelope
from config import get_settings
from services import fundamentals

router = APIRouter(prefix="/fundamentals", tags=["Fundamentals"])

_FRESHNESS = "fundamentals (FMP) — research context, not a trade trigger"


@router.get("/{ticker}", response_model=Envelope)
def fundamentals_view(ticker: str) -> Envelope:
    """Per-ticker fundamentals dashboard."""
    if not get_settings().fmp_enabled:
        return Envelope(
            ok=False, provider="fmp", freshness=_FRESHNESS,
            error="Fundamentals need an FMP key — set FMP_API_KEY.",
        )
    try:
        data = fundamentals.dashboard(ticker)
    except Exception as exc:  # noqa: BLE001 — total failure → degraded envelope
        return Envelope(ok=False, provider="fmp", freshness=_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="fmp", freshness=_FRESHNESS)
