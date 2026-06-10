"""Trade-setup signals router (ROADMAP H7).

`GET /signals/setup/{ticker}` — the per-ticker daily trade-setup bias (trend +
momentum + catalyst + smart-money + context, with relative-volume participation)
from FMP. Auth-gated like every view. Research context, never a trade trigger.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import Envelope
from config import get_settings
from services import signals

router = APIRouter(prefix="/signals", tags=["Trade Setup Signals"])

_FRESHNESS = "trade-setup context (FMP, EOD/delayed) — research only, not a trade trigger"


@router.get("/setup/{ticker}", response_model=Envelope)
def trade_setup_view(ticker: str) -> Envelope:
    """Per-ticker daily trade-setup bias."""
    if not get_settings().fmp_enabled:
        return Envelope(ok=False, provider="fmp", freshness=_FRESHNESS,
                        error="Trade setups need an FMP key — set FMP_API_KEY.")
    try:
        data = signals.trade_setup(ticker)
    except Exception as exc:  # noqa: BLE001 — total failure → degraded envelope
        return Envelope(ok=False, provider="fmp", freshness=_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="fmp", freshness=_FRESHNESS)
