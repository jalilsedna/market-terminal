"""TradingView router (ROADMAP G3).

* `POST /webhook/tradingview` — ingest endpoint for TradingView alert webhooks.
  Outside the Bearer gate (TradingView can't send headers); authenticated by the
  `tv_webhook_secret` via `?token=` or the JSON body. Must be listed in
  `app.auth.OPEN_PATHS`.
* `GET /tradingview/signals` — recent signals (auth-gated, read-only).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.schemas import Envelope
from services import tradingview as tv

router = APIRouter(tags=["TradingView"])


@router.post("/webhook/tradingview")
async def tradingview_webhook(request: Request) -> dict:
    """Receive a TradingView alert webhook (secret-gated, no Bearer)."""
    raw = (await request.body()).decode("utf-8", "replace")
    token = request.query_params.get("token")
    try:
        stored = tv.ingest(raw, url_token=token)
    except tv.WebhookDisabled as exc:
        raise HTTPException(status_code=404, detail="TradingView webhook not configured") from exc
    except tv.WebhookForbidden as exc:
        raise HTTPException(status_code=403, detail="invalid webhook token") from exc
    return {"ok": True, "stored": stored}


@router.get("/tradingview/signals", response_model=Envelope)
def tradingview_signals(limit: int = 50) -> Envelope:
    """Most-recent TradingView webhook signals (read-only)."""
    return Envelope(
        data=tv.signals(limit), provider="tradingview",
        freshness="live webhook signals — research context, not auto-executed",
    )
