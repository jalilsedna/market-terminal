"""V6 — Screener / Sector Rotation router (SPEC.md §4 V6).

Sector rotation/breadth behind the index futures, plus a pass-through equity
screener. Value-add over OpenBB's raw endpoints: the ranked sector-rotation
read (leaders/laggards) and normalized screener rows.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import Envelope
from config import get_settings
from services import movers as movers_svc
from services import screener

router = APIRouter(prefix="/screener", tags=["V6 — Screener / Sector Rotation"])

_FRESHNESS = "EOD (daily) — research context, not a tradeable signal"
_MOVERS_FRESHNESS = "whole-market EOD scan from Massive Flat Files (T+1) — research context"


@router.get("/sectors", response_model=Envelope)
def sectors() -> Envelope:
    """Sector rotation: 1d/1w/1m % change for the 11 SPDR sector ETFs, ranked."""
    try:
        data = screener.sector_rotation()
    except Exception as exc:  # noqa: BLE001 — total failure → degraded envelope
        return Envelope(ok=False, provider="yfinance", freshness=_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="yfinance", freshness=_FRESHNESS)


@router.get("/movers", response_model=Envelope)
def movers(top: int = Query(20, ge=1, le=100, description="Rows per list")) -> Envelope:
    """Whole-market top gainers/losers/most-active from Massive Flat Files."""
    if not get_settings().flatfiles_enabled:
        return Envelope(
            ok=False, provider="massive-flatfiles", freshness=_MOVERS_FRESHNESS,
            error="Movers needs Massive Flat Files — set MASSIVE_S3_ACCESS_KEY / MASSIVE_S3_SECRET_KEY.",
        )
    try:
        data = movers_svc.movers(top_n=top)
    except Exception as exc:  # noqa: BLE001 — provider failure → degraded envelope
        return Envelope(ok=False, provider="massive-flatfiles", freshness=_MOVERS_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="massive-flatfiles", freshness=_MOVERS_FRESHNESS)


@router.get("", response_model=Envelope)
def screen(
    sector: str | None = Query(None, description="e.g. 'Technology', 'Energy'"),
    industry: str | None = Query(None),
    exchange: str | None = Query(None, description="e.g. 'nasdaq', 'nyse'"),
    mktcap_min: float | None = Query(None, description="Min market cap (USD)"),
    mktcap_max: float | None = Query(None),
    price_min: float | None = Query(None),
    price_max: float | None = Query(None),
    volume_min: float | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> Envelope:
    """Run the yfinance equity screener with the given filters."""
    try:
        data = screener.run_screen(
            sector=sector, industry=industry, exchange=exchange,
            mktcap_min=mktcap_min, mktcap_max=mktcap_max,
            price_min=price_min, price_max=price_max,
            volume_min=volume_min, limit=limit,
        )
    except Exception as exc:  # noqa: BLE001 — provider failure → degraded envelope
        return Envelope(ok=False, provider="yfinance", freshness=_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="yfinance", freshness=_FRESHNESS)
