"""Analysis brief — no OpenBB/network."""

from __future__ import annotations


def test_brief_does_not_shadow_instruments_module(monkeypatch):
    """brief() must resolve registry refs; a local named `reg` caused UnboundLocalError."""
    from services import analysis
    from services import instruments as reg

    inst = reg.TrackedInstrument(
        id="crypto:BTC-USD",
        asset="crypto",
        symbol="BTC-USD",
        label="Bitcoin",
        meta={},
    )
    monkeypatch.setattr(reg, "resolve", lambda _ref: inst)
    monkeypatch.setattr(analysis, "regime", lambda: {"regime": "risk-off", "score": -2})
    monkeypatch.setattr(
        "services.watchlist.instrument_summary",
        lambda _ref: {
            "close": 100.0,
            "change_1w_pct": -1.5,
            "atr_14_pct": 2.0,
        },
    )
    monkeypatch.setattr(
        "services.news.feed",
        lambda **kwargs: {"headlines": []},
    )

    out = analysis.brief("crypto:BTC-USD")

    assert out["id"] == "crypto:BTC-USD"
    assert out["regime"]["regime"] == "risk-off"
    assert "macro regime risk-off" in out["read"]
