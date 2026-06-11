"""Decision brief composition (ROADMAP H8) — routing + fault tolerance, no network."""

from __future__ import annotations

import pytest


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


def test_equity_brief_composes_conviction_and_setup(monkeypatch):
    from services import analysis, brain, decision_brief, instruments, signals

    monkeypatch.setattr(instruments, "resolve", lambda s: (_ for _ in ()).throw(ValueError("not tracked")))
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
