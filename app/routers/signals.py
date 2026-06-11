"""Trade-setup signals router (ROADMAP H7).

`GET /signals/setup/{ticker}` — the per-ticker daily trade-setup bias (trend +
momentum + catalyst + smart-money + context, with relative-volume participation)
from FMP. Auth-gated like every view. Research context, never a trade trigger.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import Envelope
from config import get_settings
from services import market_setup, signals

router = APIRouter(prefix="/signals", tags=["Trade Setup Signals"])

_FRESHNESS = "trade-setup context (FMP, EOD/delayed) — research only, not a trade trigger"
_MKT_FRESHNESS = "technical setup (FMP, EOD/delayed) — research only, not a trade trigger"


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


@router.get("/market/{asset}/screen", response_model=Envelope)
def market_screen_view(asset: str, symbols: str | None = None, limit: int = 25) -> Envelope:
    """Rank crypto/FX technical setups across the majors (or a comma-separated list).
    Registered before the `{symbol}` route so it isn't swallowed."""
    if not get_settings().fmp_enabled:
        return Envelope(ok=False, provider="fmp", freshness=_MKT_FRESHNESS,
                        error="Market setups need an FMP key — set FMP_API_KEY.")
    syms = [s for s in (symbols or "").split(",") if s.strip()] or None
    try:
        data = market_setup.screen(asset, symbols=syms, limit=limit)
    except ValueError as exc:
        return Envelope(ok=False, provider="fmp", freshness=_MKT_FRESHNESS, error=str(exc))
    except Exception as exc:  # noqa: BLE001 — degrade rather than 500
        return Envelope(ok=False, provider="fmp", freshness=_MKT_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="fmp", freshness=_MKT_FRESHNESS)


@router.get("/market/{asset}/{symbol:path}", response_model=Envelope)
def market_setup_view(asset: str, symbol: str) -> Envelope:
    """Per-symbol crypto/FX technical setup (trend + momentum + participation)."""
    if not get_settings().fmp_enabled:
        return Envelope(ok=False, provider="fmp", freshness=_MKT_FRESHNESS,
                        error="Market setups need an FMP key — set FMP_API_KEY.")
    try:
        data = market_setup.market_setup(asset, symbol)
    except ValueError as exc:
        return Envelope(ok=False, provider="fmp", freshness=_MKT_FRESHNESS, error=str(exc))
    except Exception as exc:  # noqa: BLE001 — degrade rather than 500
        return Envelope(ok=False, provider="fmp", freshness=_MKT_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="fmp", freshness=_MKT_FRESHNESS)


@router.get("/hitlist", response_model=Envelope)
def daily_hitlist_view(limit: int = 15, scan_depth: int = 20, min_move_pct: float = 2.0) -> Envelope:
    """Market-wide morning scanner: today's movers ranked with a directional lean."""
    if not get_settings().fmp_enabled:
        return Envelope(ok=False, provider="fmp + polygon", freshness=_FRESHNESS,
                        error="Hit-list needs an FMP key — set FMP_API_KEY.")
    try:
        data = signals.daily_hitlist(limit=limit, scan_depth=scan_depth, min_move_pct=min_move_pct)
    except Exception as exc:  # noqa: BLE001 — total failure → degraded envelope
        return Envelope(ok=False, provider="fmp + polygon", freshness=_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="fmp + polygon", freshness=_FRESHNESS)
