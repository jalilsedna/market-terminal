"""TradingView webhook signals (ROADMAP G3).

TradingView Pro+ alerts (including Pine `alert()` calls and strategy entries/
exits) can POST a webhook to a URL — but TradingView can't send custom auth
headers, so this endpoint lives OUTSIDE the Bearer gate and is authenticated by a
**shared secret** (`tv_webhook_secret`) passed in the URL `?token=` or the JSON
body's `token` field. Signals are stored in SQLite, surfaced read-only in the UI
(Chart tab) and over MCP (`tradingview_signals`) so Alice can see them — the
terminal never acts on them (research-only).

Note: there is no TradingView API to read your saved Pine scripts; webhooks are
the supported way to get strategy *signals* out. Pure + dependency-light
(config + db, stdlib `json`/`hmac`), so it's unit-tested in CI.
"""

from __future__ import annotations

import hmac
import json

from app import db
from config import get_settings


class WebhookDisabled(RuntimeError):
    """No `tv_webhook_secret` configured → the webhook is off (router → 404)."""


class WebhookForbidden(RuntimeError):
    """Token missing or wrong (router → 403)."""


def _coerce(value: object) -> str | None:
    return None if value is None else str(value)


def _parse(raw_body: str) -> dict:
    """Parse the webhook body. JSON if possible, else treat it as a text message."""
    raw_body = (raw_body or "").strip()
    if not raw_body:
        return {}
    try:
        parsed = json.loads(raw_body)
        return parsed if isinstance(parsed, dict) else {"text": raw_body}
    except (ValueError, TypeError):
        return {"text": raw_body}


def ingest(raw_body: str, url_token: str | None = None) -> dict:
    """Validate the secret and store a TradingView signal. Returns the stored
    record (without the secret). Raises WebhookDisabled / WebhookForbidden."""
    secret = get_settings().tv_webhook_secret
    if not secret:
        raise WebhookDisabled("tv_webhook_secret not configured")

    payload = _parse(raw_body)
    token = url_token or payload.get("token")
    if not token or not hmac.compare_digest(str(token), secret):
        raise WebhookForbidden("missing or invalid token")

    # Map common TradingView alert fields; keep the full raw body regardless.
    ticker = _coerce(payload.get("ticker") or payload.get("symbol"))
    action = _coerce(payload.get("action") or payload.get("side") or payload.get("order_action"))
    price = _coerce(payload.get("price") or payload.get("close"))
    text = _coerce(payload.get("text") or payload.get("message") or payload.get("alert"))
    if text is None and "text" in payload:
        text = _coerce(payload["text"])

    signal_id = db.tv_signal_add(ticker, action, price, text, raw_body)
    return {"id": signal_id, "ticker": ticker, "action": action, "price": price, "text": text}


def signals(limit: int = 50) -> dict:
    """Recent TradingView signals (newest first)."""
    return {
        "count": len(rows := db.tv_signal_list(limit)),
        "enabled": bool(get_settings().tv_webhook_secret),
        "signals": rows,
        "disclaimer": "TradingView strategy/alert signals — research context, not auto-executed.",
    }
