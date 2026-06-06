"""Analysis router — interpreted signals (ROADMAP C3).

Value-add over the raw views: these endpoints *interpret* the data (positioning
extremes, macro regime) into a structured read for human review — explicitly
research context, never a trade trigger. Pattern adapted from
anthropics/financial-services (Apache-2.0); analytics built for this terminal's
futures/macro domain.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import Envelope
from services import analysis

router = APIRouter(prefix="/analysis", tags=["Analysis (interpreted signals)"])

_FRESHNESS = "derived from EOD/weekly views — research context, not a signal"


@router.get("/cot", response_model=Envelope)
def cot_signals() -> Envelope:
    """COT positioning read across the watchlist (contrarian-at-extremes lens)."""
    return Envelope(data=analysis.cot_signals(), provider="derived (cftc)", freshness=_FRESHNESS)


@router.get("/regime", response_model=Envelope)
def regime() -> Envelope:
    """Risk-on / risk-off macro regime read (VIX, sector breadth, dollar, index)."""
    return Envelope(data=analysis.regime(), provider="derived (mixed)", freshness=_FRESHNESS)


@router.get("/brief", response_model=Envelope)
def brief(instrument: str = Query(..., description="Watchlist code, e.g. 'GC', '6E'")) -> Envelope:
    """"What's moving this contract" — per-instrument synthesis of regime,
    positioning, price/momentum, term structure, and tagged news."""
    try:
        data = analysis.brief(instrument)
    except ValueError as exc:  # unknown instrument
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Envelope(data=data, provider="derived (mixed)", freshness=_FRESHNESS)


@router.get("/term-structure", response_model=Envelope)
def term_structure_signal(
    lookback_days: int = Query(7, ge=1, le=90, description="Days back for the comparison"),
) -> Envelope:
    """Contango↔backwardation flips + steepening across the curves (now vs ~Nd ago)."""
    return Envelope(data=analysis.term_structure_signal(lookback_days),
                    provider="derived (cboe/yfinance)", freshness=_FRESHNESS)
