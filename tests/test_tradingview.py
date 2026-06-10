"""TradingView webhook ingest + signals (ROADMAP G3) — no OpenBB/network."""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def tv(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("TV_WEBHOOK_SECRET", "s3cret")
    import config

    config.get_settings.cache_clear()
    from services import tradingview as svc

    yield svc
    config.get_settings.cache_clear()


def test_disabled_without_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.delenv("TV_WEBHOOK_SECRET", raising=False)
    import config

    config.get_settings.cache_clear()
    from services import tradingview as svc

    with pytest.raises(svc.WebhookDisabled):
        svc.ingest('{"ticker":"AAPL"}', url_token="anything")
    config.get_settings.cache_clear()


def test_forbidden_on_bad_or_missing_token(tv):
    with pytest.raises(tv.WebhookForbidden):
        tv.ingest('{"ticker":"AAPL"}', url_token="wrong")
    with pytest.raises(tv.WebhookForbidden):
        tv.ingest('{"ticker":"AAPL"}', url_token=None)  # no token anywhere


def test_ingest_json_with_url_token(tv):
    rec = tv.ingest(
        json.dumps({"ticker": "AAPL", "action": "buy", "price": 191.2, "text": "breakout"}),
        url_token="s3cret",
    )
    assert rec["ticker"] == "AAPL" and rec["action"] == "buy"
    assert rec["price"] == "191.2" and rec["text"] == "breakout"
    out = tv.signals()
    assert out["enabled"] is True and out["count"] == 1
    assert out["signals"][0]["ticker"] == "AAPL"


def test_ingest_token_in_body(tv):
    rec = tv.ingest(json.dumps({"token": "s3cret", "symbol": "GLD", "side": "sell"}))
    assert rec["ticker"] == "GLD" and rec["action"] == "sell"


def test_ingest_plain_text_body(tv):
    # token must still come via URL since the body isn't JSON
    rec = tv.ingest("GC long signal fired", url_token="s3cret")
    assert rec["text"] == "GC long signal fired"
    assert rec["ticker"] is None


def test_signals_newest_first(tv):
    tv.ingest(json.dumps({"ticker": "A"}), url_token="s3cret")
    tv.ingest(json.dumps({"ticker": "B"}), url_token="s3cret")
    out = tv.signals()
    assert [s["ticker"] for s in out["signals"]] == ["B", "A"]
