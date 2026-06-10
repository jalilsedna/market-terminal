"""Brain router (ROADMAP H5) — the synthesized decision result.

`GET /brain/{ticker}` returns the fused conviction verdict (bottom-up fundamentals
+ top-down macro) plus the underlying fundamentals dashboard, so the Fundamentals
tab can lead with a *result* rather than just data. Auth-gated.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import Envelope
from config import get_settings
from services import brain, brain_crypto, brain_forex

router = APIRouter(prefix="/brain", tags=["Brain"])

_FRESHNESS = "synthesized conviction (fundamentals + macro) — research, not a trade trigger"
_CRYPTO_FRESHNESS = "synthesized crypto conviction (momentum + macro + vol) — research, not a trade trigger"
_FOREX_FRESHNESS = "synthesized forex conviction (momentum + macro + vol) — research, not a trade trigger"


@router.get("/crypto/screen", response_model=Envelope)
def crypto_brain_screen(
    symbols: str | None = Query(None, description="Comma-separated registry refs; omit = all crypto"),
    limit: int = Query(25, ge=1, le=200),
) -> Envelope:
    syms = [s for s in (symbols or "").split(",") if s.strip()] or None
    try:
        data = brain_crypto.screen(symbols=syms, limit=limit)
    except ValueError as exc:
        return Envelope(ok=False, provider="terminal-brain-crypto", freshness=_CRYPTO_FRESHNESS,
                        error=str(exc))
    except Exception as exc:  # noqa: BLE001
        return Envelope(ok=False, provider="terminal-brain-crypto", freshness=_CRYPTO_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="terminal-brain-crypto", freshness=_CRYPTO_FRESHNESS)


@router.get("/crypto/{instrument:path}", response_model=Envelope)
def crypto_brain_view(instrument: str) -> Envelope:
    try:
        data = brain_crypto.verdict(instrument)
    except ValueError as exc:
        return Envelope(ok=False, provider="terminal-brain-crypto", freshness=_CRYPTO_FRESHNESS,
                        error=str(exc))
    except Exception as exc:  # noqa: BLE001
        return Envelope(ok=False, provider="terminal-brain-crypto", freshness=_CRYPTO_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="terminal-brain-crypto", freshness=_CRYPTO_FRESHNESS)


@router.get("/forex/screen", response_model=Envelope)
def forex_brain_screen(
    symbols: str | None = Query(None, description="Comma-separated registry refs; omit = all forex"),
    limit: int = Query(25, ge=1, le=200),
) -> Envelope:
    syms = [s for s in (symbols or "").split(",") if s.strip()] or None
    try:
        data = brain_forex.screen(symbols=syms, limit=limit)
    except ValueError as exc:
        return Envelope(ok=False, provider="terminal-brain-forex", freshness=_FOREX_FRESHNESS,
                        error=str(exc))
    except Exception as exc:  # noqa: BLE001
        return Envelope(ok=False, provider="terminal-brain-forex", freshness=_FOREX_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="terminal-brain-forex", freshness=_FOREX_FRESHNESS)


@router.get("/forex/{instrument:path}", response_model=Envelope)
def forex_brain_view(instrument: str) -> Envelope:
    try:
        data = brain_forex.verdict(instrument)
    except ValueError as exc:
        return Envelope(ok=False, provider="terminal-brain-forex", freshness=_FOREX_FRESHNESS,
                        error=str(exc))
    except Exception as exc:  # noqa: BLE001
        return Envelope(ok=False, provider="terminal-brain-forex", freshness=_FOREX_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="terminal-brain-forex", freshness=_FOREX_FRESHNESS)


@router.get("/screen", response_model=Envelope)
def brain_screen(
    symbols: str | None = Query(None, description="Comma-separated tickers; omit to screen the registry"),
    limit: int = Query(25, ge=1, le=200),
) -> Envelope:
    """Conviction ranking across a universe — explicit `symbols` or the registry's
    fundamentals-capable instruments (equities/ETFs). Registered before `/{ticker}`
    so it isn't swallowed by the path param."""
    if not get_settings().fmp_enabled:
        return Envelope(ok=False, provider="terminal-brain", freshness=_FRESHNESS,
                        error="The brain needs fundamentals — set FMP_API_KEY.")
    syms = [s for s in (symbols or "").split(",") if s.strip()] or None
    try:
        data = brain.screen(symbols=syms, limit=limit)
    except Exception as exc:  # noqa: BLE001 — degrade rather than 500
        return Envelope(ok=False, provider="terminal-brain", freshness=_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="terminal-brain", freshness=_FRESHNESS)


@router.get("/{ticker}", response_model=Envelope)
def brain_view(ticker: str) -> Envelope:
    """Fused per-ticker conviction verdict + the fundamentals it rests on."""
    if not get_settings().fmp_enabled:
        return Envelope(ok=False, provider="terminal-brain", freshness=_FRESHNESS,
                        error="The brain needs fundamentals — set FMP_API_KEY.")
    try:
        data = brain.verdict(ticker)
    except Exception as exc:  # noqa: BLE001 — degrade rather than 500
        return Envelope(ok=False, provider="terminal-brain", freshness=_FRESHNESS,
                        error=f"{type(exc).__name__}: {exc}"[:200])
    return Envelope(data=data, provider="terminal-brain", freshness=_FRESHNESS)
