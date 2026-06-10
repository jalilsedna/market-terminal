"""Decision brain (ROADMAP H5) — synthesis scoring + verdict (no OpenBB/network)."""

from __future__ import annotations


def test_macro_lean():
    from services.brain import _macro_lean

    assert _macro_lean("risk-on") == 1
    assert _macro_lean("risk-off") == -1
    assert _macro_lean("mixed / neutral") == 0
    assert _macro_lean(None) == 0


def test_score_and_conviction():
    from services.brain import _conviction, _score

    bu, an = _score({"valuation": "cheap", "quality": "strong", "growth": "growing"}, 0.15)
    assert bu == 3 and an == 1
    assert _conviction(bu + an + 1) == "constructive"  # + risk-on macro

    bu2, an2 = _score({"valuation": "expensive", "quality": "weak", "growth": "declining"}, -0.2)
    assert bu2 == -3 and an2 == -1
    assert _conviction(bu2 + an2 - 1) == "cautious"
    assert _conviction(0) == "neutral"


def test_verdict_constructive(monkeypatch):
    from services import analysis, brain, fundamentals

    monkeypatch.setattr(fundamentals, "dashboard", lambda s: {
        "symbol": s,
        "read": {
            "verdict": "cheap (DCF +22%) · strong quality · growing",
            "labels": {"valuation": "cheap", "quality": "strong", "growth": "growing"},
            "flags": ["earnings in 9d — event risk"],
        },
        "analyst": {"upside": 0.15},
    })
    monkeypatch.setattr(analysis, "regime", lambda: {"regime": "risk-on", "score": 3})

    v = brain.verdict("aapl")
    assert v["symbol"] == "AAPL"
    assert v["conviction"] == "constructive"
    assert v["components"]["bottom_up"] == 3 and v["components"]["macro"] == 1
    assert "CONSTRUCTIVE" in v["summary"].upper()
    assert v["flags"]  # event-risk carried through


def test_verdict_insufficient(monkeypatch):
    from services import analysis, brain, fundamentals

    monkeypatch.setattr(fundamentals, "dashboard", lambda s: {"symbol": s, "read": {"labels": {}, "flags": []}, "analyst": {}})
    monkeypatch.setattr(analysis, "regime", lambda: {"regime": "mixed / neutral"})
    assert brain.verdict("ZZZ")["conviction"] == "insufficient"


def test_verdict_degrades_when_macro_fails(monkeypatch):
    from services import analysis, brain, fundamentals

    monkeypatch.setattr(fundamentals, "dashboard", lambda s: {
        "symbol": s,
        "read": {"verdict": "x", "labels": {"valuation": "cheap", "quality": "strong", "growth": "growing"}, "flags": []},
        "analyst": {"upside": 0.0},
    })

    def boom():
        raise RuntimeError("openbb down")

    monkeypatch.setattr(analysis, "regime", boom)
    v = brain.verdict("AAPL")
    assert v["components"]["macro"] == 0  # macro input failed → 0, brain still produces a result
    assert v["conviction"] == "constructive"  # bottom-up 3 alone
