"""Decision brief composition (ROADMAP H8) — routing + fault tolerance, no network."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _stub_news_pulse(monkeypatch):
    """Keep brief() composition deterministic — the pulse section is tested in
    tests/test_news_pulse.py and has its own underlying calls."""
    from services import news_pulse
    monkeypatch.setattr(news_pulse, "pulse", lambda symbol, asset=None: {
        "direction": "neutral", "confidence": "low", "engine": "rule-based",
        "summary": f"{symbol} stub", "catalysts": [],
    })


def test_infer_asset():
    from services.decision_brief import _infer_asset

    assert _infer_asset("GC=F") == "futures"
    assert _infer_asset("BTC-USD") == "crypto"
    assert _infer_asset("EURUSD") == "forex"
    assert _infer_asset("AAPL") == "equity"


def test_requires_symbol():
    from services import decision_brief

    with pytest.raises(ValueError):
        decision_brief.brief("")


def test_brief_includes_news_pulse_section(monkeypatch):
    from services import analysis, brain, decision_brief, instruments, news_pulse, signals

    monkeypatch.setattr(instruments, "resolve", lambda s: (_ for _ in ()).throw(ValueError("nt")))
    monkeypatch.setattr(instruments, "ensure", lambda *a, **k: (_ for _ in ()).throw(ValueError("nt")))
    monkeypatch.setattr(analysis, "regime", lambda: {"regime": "risk-off", "score": -2})
    monkeypatch.setattr(brain, "verdict", lambda s: {"conviction": "neutral"})
    monkeypatch.setattr(signals, "trade_setup", lambda s: {"bias": "long"})
    monkeypatch.setattr(news_pulse, "pulse", lambda symbol, asset=None: {
        "direction": "up", "confidence": "high", "engine": "llm",
        "summary": "fresh upgrades", "catalysts": ["analyst upgrade"]})

    out = decision_brief.brief("AAPL")
    assert out["sections"]["news_pulse"]["direction"] == "up"
    assert out["sections"]["news_pulse"]["engine"] == "llm"
    assert "24H NEWS UP" in out["synthesis"].upper()


def test_equity_brief_composes_conviction_and_setup(monkeypatch):
    from services import analysis, brain, decision_brief, instruments, signals

    monkeypatch.setattr(instruments, "resolve", lambda s: (_ for _ in ()).throw(ValueError("not tracked")))
    monkeypatch.setattr(instruments, "ensure", lambda *a, **k: (_ for _ in ()).throw(ValueError("not tracked")))
    monkeypatch.setattr(analysis, "regime", lambda: {"regime": "risk-off", "score": -2})
    monkeypatch.setattr(brain, "verdict", lambda s: {"conviction": "neutral", "score": 2})
    monkeypatch.setattr(signals, "trade_setup", lambda s: {"bias": "long", "in_play": True})

    out = decision_brief.brief("AAPL")
    assert out["asset"] == "equity" and out["in_registry"] is False
    assert out["macro"]["regime"] == "risk-off"
    assert out["sections"]["conviction"]["conviction"] == "neutral"
    assert out["sections"]["setup"]["bias"] == "long"
    assert "CONVICTION NEUTRAL" in out["synthesis"].upper()
    assert "SETUP LONG" in out["synthesis"].upper()
    assert "risk-off" in out["synthesis"]
    assert out["errors"] is None
    assert out["skipped"]["volatility"] == out["skipped"]["news"]
    assert "not in registry" in out["skipped"]["volatility"]


def test_crypto_brief_uses_market_setup(monkeypatch):
    from services import analysis, decision_brief, instruments, market_setup

    monkeypatch.setattr(instruments, "resolve", lambda s: (_ for _ in ()).throw(ValueError("nt")))
    monkeypatch.setattr(analysis, "regime", lambda: {"regime": "mixed / neutral", "score": 0})
    monkeypatch.setattr(market_setup, "market_setup", lambda a, s: {"bias": "short", "in_play": False})

    out = decision_brief.brief("BTC-USD")
    assert out["asset"] == "crypto"
    assert out["sections"]["setup"]["bias"] == "short"
    # No registry id → no crypto-brain conviction section attempted.
    assert "conviction" not in out["sections"]
    assert "conviction" in out["skipped"]
    assert "not in registry" in out["skipped"]["conviction"]


def test_equity_brief_auto_registers_for_vol_news(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "terminal.db"))
    import config

    config.get_settings.cache_clear()
    from services import analysis, brain, decision_brief, news, signals, volatility

    monkeypatch.setattr(analysis, "regime", lambda: {"regime": "mixed / neutral", "score": 0})
    monkeypatch.setattr(brain, "verdict", lambda s: {"conviction": "cautious"})
    monkeypatch.setattr(signals, "trade_setup", lambda s: {"bias": "long"})
    monkeypatch.setattr(volatility, "volatility", lambda _id: {"regime": "normal", "as_of": "2026-06-10"})
    monkeypatch.setattr(
        news,
        "feed",
        lambda **kwargs: {"headlines": [{"title": "CBRL insider buying", "date": "2026-06-11"}]},
    )

    out = decision_brief.brief("CBRL")
    assert out["in_registry"] is True
    assert out["sections"]["volatility"]["regime"] == "normal"
    assert out["sections"]["news"][0]["title"] == "CBRL insider buying"
    assert out["skipped"] is None or "volatility" not in (out["skipped"] or {})
    config.get_settings.cache_clear()


def test_registry_equity_empty_news_is_skipped_not_silent(monkeypatch):
    from services import analysis, brain, decision_brief, instruments, news, signals, volatility

    inst = instruments.TrackedInstrument(
        id="equity:CBRL",
        asset="equity",
        symbol="CBRL",
        label="Cracker Barrel",
        meta={},
    )
    monkeypatch.setattr(instruments, "resolve", lambda _s: inst)
    monkeypatch.setattr(analysis, "regime", lambda: {"regime": "mixed / neutral", "score": 0})
    monkeypatch.setattr(brain, "verdict", lambda s: {"conviction": "neutral"})
    monkeypatch.setattr(signals, "trade_setup", lambda s: {"bias": "long"})
    monkeypatch.setattr(volatility, "volatility", lambda _id: {"regime": "normal"})
    monkeypatch.setattr(news, "feed", lambda **kwargs: {"headlines": []})

    out = decision_brief.brief("CBRL")
    assert out["in_registry"] is True
    assert "volatility" in out["sections"]
    assert "news" not in out["sections"]
    assert out["skipped"]["news"] == "no headlines tagged to this symbol"
    assert out["errors"] is None


def test_section_failure_is_isolated(monkeypatch):
    from services import analysis, brain, decision_brief, instruments, signals

    monkeypatch.setattr(instruments, "resolve", lambda s: (_ for _ in ()).throw(ValueError("nt")))
    monkeypatch.setattr(analysis, "regime", lambda: {"regime": "risk-on", "score": 2})

    def boom(s):
        raise RuntimeError("provider down")

    monkeypatch.setattr(brain, "verdict", boom)
    monkeypatch.setattr(signals, "trade_setup", lambda s: {"bias": "neutral"})

    out = decision_brief.brief("AAPL")
    assert out["errors"] and "conviction" in out["errors"]  # surfaced
    assert out["sections"]["setup"]["bias"] == "neutral"  # the rest still composed
