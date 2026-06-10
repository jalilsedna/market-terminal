"""V3 — News Feed router (SPEC.md §4 V3).

Merged world/macro news, deduped and newest-first, each headline tagged with the
watchlist instrument(s) / macro theme it affects. Value-add over OpenBB's raw
news: dedupe + instrument tagging + relevance filtering, not a passthrough.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import Envelope
from services import news

router = APIRouter(prefix="/news", tags=["V3 — News Feed"])

_FRESHNESS = "near-real-time headlines (cached ~15m) — research context, not a signal"


@router.get("", response_model=Envelope)
def news_feed(
    limit: int = Query(50, ge=1, le=200, description="Max headlines to return"),
    instrument: str | None = Query(None, description="Filter to one instrument, e.g. 'GC'"),
    provider: str = Query("fmp", description="News provider (requires FMP_API_KEY)"),
) -> Envelope:
    """Merged, instrument-tagged, deduped news feed across the watchlist."""
    try:
        data = news.feed(limit=limit, instrument=instrument, provider=provider)
    except ValueError as exc:  # unknown instrument → client error
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — provider failure → degraded envelope
        return Envelope(ok=False, provider=provider, freshness=_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider=provider, freshness=_FRESHNESS)
