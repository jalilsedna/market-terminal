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
_MOVERS_FRESHNESS = "whole-market EOD scan (Polygon/Massive Grouped Daily) — research context"


@router.get("/sectors", response_model=Envelope)
def sectors() -> Envelope:
    """Sector rotation: 1d/1w/1m % change for the 11 SPDR sector ETFs, ranked."""
    try:
        data = screener.sector_rotation()
    except Exception as exc:  # noqa: BLE001 — total failure → degraded envelope
        return Envelope(ok=False, provider="fmp", freshness=_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="fmp", freshness=_FRESHNESS)


@router.get("/movers", response_model=Envelope)
def movers(top: int = Query(20, ge=1, le=100, description="Rows per list")) -> Envelope:
    """Whole-market top gainers/losers/most-active from Massive Flat Files."""
    if not get_settings().movers_enabled:
        return Envelope(
            ok=False, provider="polygon", freshness=_MOVERS_FRESHNESS,
            error="Movers needs a Polygon/Massive key — set POLYGON_API_KEY.",
        )
    try:
        data = movers_svc.movers(top_n=top)
    except Exception as exc:  # noqa: BLE001 — provider failure → degraded envelope
        return Envelope(ok=False, provider="polygon", freshness=_MOVERS_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="polygon", freshness=_MOVERS_FRESHNESS)


@router.get("", response_model=Envelope)
def screen(
    sector: str | None = Query(None, description="e.g. 'Technology', 'Energy'"),
    industry: str | None = Query(None),
    exchange: str | None = Query(None, description="e.g. 'NASDAQ', 'NYSE'"),
    country: str | None = Query(None, description="e.g. 'US'"),
    mktcap_min: float | None = Query(None, description="Min market cap (USD)"),
    mktcap_max: float | None = Query(None),
    price_min: float | None = Query(None),
    price_max: float | None = Query(None),
    volume_min: float | None = Query(None),
    beta_min: float | None = Query(None),
    beta_max: float | None = Query(None, description="Max beta (e.g. <1 for low-vol)"),
    dividend_min: float | None = Query(None, description="Min annual dividend $"),
    limit: int = Query(50, ge=1, le=1000),
) -> Envelope:
    """Fundamental equity screener (FMP): filter the universe by cap/price/beta/
    dividend/volume/sector/industry/exchange/country."""
    try:
        data = screener.run_screen(
            sector=sector, industry=industry, exchange=exchange, country=country,
            mktcap_min=mktcap_min, mktcap_max=mktcap_max,
            price_min=price_min, price_max=price_max, volume_min=volume_min,
            beta_min=beta_min, beta_max=beta_max, dividend_min=dividend_min, limit=limit,
        )
    except Exception as exc:  # noqa: BLE001 — provider failure → degraded envelope
        return Envelope(ok=False, provider="fmp", freshness=_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="fmp", freshness=_FRESHNESS)
