"""Analysis brief — no OpenBB/network."""

from __future__ import annotations

import math


def test_regime_omits_nan_spx_1w(monkeypatch):
    """Non-finite index % changes must not surface as +nan% in the regime vote."""
    from cache.store import clear as clear_cache
    from services import analysis, macro as macro_svc

    clear_cache()
    monkeypatch.setattr(
        macro_svc,
        "build_dashboard",
        lambda: {
            "dollar_fx": {"ok": True, "dollar_index": {"change_1w_pct": 0.5}},
            "indices": {
                "ok": True,
                "indices": {
                    "^GSPC": {"label": "S&P 500 (ES)", "change_1w_pct": math.nan},
                },
            },
        },
    )
    monkeypatch.setattr("services.term_structure.dashboard", lambda: {})
    monkeypatch.setattr("services.screener.sector_rotation", lambda: {"leaders": []})

    out = analysis.regime()
    names = [s["name"] for s in out["signals"]]
    assert "S&P 500 (1w)" not in names
    assert any(s["name"] == "Broad USD (1w)" for s in out["signals"])


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
