"""Crypto / forex brain — pure scoring + wiring (no OpenBB/network)."""

from __future__ import annotations


def test_market_scoring_helpers():
    from services.brain_common import (
        macro_lean,
        market_conviction,
        momentum_vote,
        usd_headwind_crypto,
        usd_vote_forex,
        vol_vote,
    )

    assert macro_lean("risk-on") == 1
    assert momentum_vote(2.0, 1.0) == 1
    assert momentum_vote(-2.0, -1.0) == -1
    assert vol_vote("stressed") == (-1, ["stressed vol — sizing caution"])
    assert usd_headwind_crypto(0.5) == -1
    assert usd_vote_forex("EURUSD", 0.5) == -1
    assert usd_vote_forex("USDJPY", 0.5) == 1
    assert market_conviction(2) == "constructive"
    assert market_conviction(-2) == "cautious"


def test_crypto_verdict_constructive(monkeypatch):
    from services import analysis, brain_crypto
    from services import instruments as reg
    from services import macro as macro_svc
    from services import volatility as vol_svc
    from services import watchlist as wl_svc

    inst = reg.TrackedInstrument(
        id="crypto:BTC-USD",
        asset="crypto",
        symbol="BTC-USD",
        label="Bitcoin",
        meta={},
    )
    monkeypatch.setattr(reg, "resolve", lambda _ref: inst)
    monkeypatch.setattr(analysis, "regime", lambda: {"regime": "risk-on"})
    monkeypatch.setattr(macro_svc, "build_dashboard", lambda: {
        "dollar_fx": {"ok": True, "dollar_index": {"change_1w_pct": -0.5}},
    })
    monkeypatch.setattr(wl_svc, "instrument_summary", lambda _ref: {
        "ok": True,
        "last": 100.0,
        "change_1w_pct": 3.0,
        "change_1m_pct": 5.0,
        "vol_annualized": 0.5,
        "regime": "normal",
    })
    monkeypatch.setattr(vol_svc, "volatility", lambda _ref: {
        "ok": True,
        "regime": {"regime": "normal", "percentile": 50},
    })

    v = brain_crypto.verdict("crypto:BTC-USD")
    assert v["conviction"] == "constructive"
    assert v["components"]["momentum"] == 1
    assert v["components"]["macro"] == 1
    assert "price" in v


def test_forex_screen_registry(monkeypatch):
    from services import analysis, brain_forex
    from services import instruments as reg
    from services import macro as macro_svc
    from services import watchlist as wl_svc

    class _Inst:
        def __init__(self, item_id: str, symbol: str):
            self.id = item_id
            self.asset = "forex"
            self.symbol = symbol
            self.label = symbol

    monkeypatch.setattr(reg, "list_all", lambda: [_Inst("forex:EURUSD", "EURUSD")])
    monkeypatch.setattr(analysis, "regime", lambda: {"regime": "risk-off"})
    monkeypatch.setattr(macro_svc, "build_dashboard", lambda: {
        "dollar_fx": {"ok": True, "dollar_index": {"change_1w_pct": 0.0}},
    })
    monkeypatch.setattr(wl_svc, "instrument_summary", lambda _ref: {
        "ok": True,
        "last": 1.08,
        "change_1w_pct": -1.0,
        "change_1m_pct": -0.5,
        "regime": "normal",
    })

    out = brain_forex.screen()
    assert out["universe"] == "registry"
    assert out["ranked"][0]["symbol"] == "EURUSD"
    assert out["ranked"][0]["components"]["momentum"] == -1
