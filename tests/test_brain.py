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


def _fund(labels, upside):
    return lambda s: {"symbol": s, "read": {"verdict": "x", "labels": labels, "flags": []}, "analyst": {"upside": upside}}


def test_screen_explicit_symbols_ranked(monkeypatch):
    from services import analysis, brain, fundamentals

    reads = {
        "AAPL": ({"valuation": "cheap", "quality": "strong", "growth": "growing"}, 0.2),
        "XYZ": ({"valuation": "expensive", "quality": "weak", "growth": "declining"}, -0.2),
    }
    monkeypatch.setattr(fundamentals, "dashboard",
                        lambda s: _fund(*reads[s.upper()])(s))
    monkeypatch.setattr(analysis, "regime", lambda: {"regime": "risk-on"})

    out = brain.screen(symbols=["aapl", "xyz"])
    assert out["count"] == 2 and out["universe"] == "explicit"
    ranked = out["ranked"]
    assert ranked[0]["symbol"] == "AAPL" and ranked[0]["conviction"] == "constructive"
    assert ranked[-1]["symbol"] == "XYZ" and ranked[-1]["conviction"] == "cautious"
    # Compact rows: no nested fundamentals payload in a screen.
    assert "fundamentals" not in ranked[0]


def test_screen_registry_universe_filters_to_fundamentals(monkeypatch):
    from services import analysis, brain, fundamentals, instruments

    class _Inst:
        def __init__(self, symbol, fund):
            self.symbol = symbol
            self._fund = fund

        def capabilities(self):
            return {"fundamentals": self._fund}

    monkeypatch.setattr(instruments, "list_all",
                        lambda: [_Inst("AAPL", True), _Inst("GC=F", False)])
    monkeypatch.setattr(fundamentals, "dashboard",
                        lambda s: _fund({"valuation": "cheap", "quality": "strong", "growth": "growing"}, 0.2)(s))
    monkeypatch.setattr(analysis, "regime", lambda: {"regime": "risk-on"})

    out = brain.screen()
    assert out["universe"] == "registry"
    assert [r["symbol"] for r in out["ranked"]] == ["AAPL"]  # futures excluded


def test_screen_bad_symbol_does_not_sink(monkeypatch):
    from services import analysis, brain, fundamentals

    def dash(s):
        if s.upper() == "BAD":
            raise RuntimeError("provider blew up")
        return _fund({"valuation": "cheap", "quality": "strong", "growth": "growing"}, 0.2)(s)

    monkeypatch.setattr(fundamentals, "dashboard", dash)
    monkeypatch.setattr(analysis, "regime", lambda: {"regime": "risk-on"})

    out = brain.screen(symbols=["AAPL", "BAD"])
    by = {r["symbol"]: r for r in out["ranked"]}
    assert by["AAPL"]["conviction"] == "constructive"
    assert by["BAD"]["conviction"] == "error"
    assert by["AAPL"]["score"] > (by["BAD"]["score"] or -99)  # errors sink to the bottom
