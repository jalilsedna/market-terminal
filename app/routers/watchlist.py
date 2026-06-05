"""V2 — Watchlist router (SPEC.md §4 V2).

The user's fixed watchlist (6E/6B/GC/NQ/YM): EOD OHLCV, 1d/1w/1m % change,
ATR(14), each beside its spot/cash proxy. Value-add over OpenBB's raw endpoints:
it merges future + proxy, computes change/ATR, and keys off the explicit symbol
map — not a 1:1 passthrough.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import Envelope
from services import watchlist

router = APIRouter(prefix="/watchlist", tags=["V2 — Watchlist"])

_FRESHNESS = "EOD (daily) — research context, not a tradeable signal"


@router.get("", response_model=Envelope)
def watchlist_all() -> Envelope:
    """Full watchlist summary (each instrument fault-tolerant)."""
    return Envelope(data=watchlist.watchlist(), provider="yfinance", freshness=_FRESHNESS)


@router.get("/{code}", response_model=Envelope)
def watchlist_one(code: str) -> Envelope:
    """One instrument by watchlist shorthand (e.g. 'GC', '6E')."""
    try:
        data = watchlist.instrument_summary(code)
    except ValueError as exc:  # unknown instrument → client error
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — provider failure → degraded envelope
        return Envelope(ok=False, provider="yfinance", freshness=_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="yfinance", freshness=_FRESHNESS)
