"""Cash-index history — FMP-first with ETF fallback (regime S&P 1w)."""

from __future__ import annotations

import math

import pytest


def _bars(n: int, *, start: float = 100.0, step: float = 0.5) -> list[dict]:
    return [
        {"date": f"2026-01-{i+1:02d}", "close": start + i * step}
        for i in range(n)
    ]


def test_index_history_uses_fmp_when_usable(monkeypatch):
    from cache.store import clear as clear_cache
    from obb_layer import macro as obb_macro

    clear_cache()
    calls: list[str] = []

    def fake_history(sym):
        calls.append(sym)
        return _bars(10)

    monkeypatch.setattr("obb_layer.fmp_market.history", fake_history)
    rows = obb_macro.index_history("^GSPC")
    assert len(rows) == 10
    assert calls == ["^GSPC"]


def test_index_history_falls_back_to_spy(monkeypatch):
    from cache.store import clear as clear_cache
    from obb_layer import macro as obb_macro

    clear_cache()
    def fake_history(sym):
        if sym == "^GSPC":
            return _bars(3)  # too short
        if sym == "SPY":
            return _bars(10, start=500.0)
        raise AssertionError(sym)

    monkeypatch.setattr("obb_layer.fmp_market.history", fake_history)
    rows = obb_macro.index_history("^GSPC")
    assert len(rows) == 10
    assert rows[-1]["close"] == 500.0 + 9 * 0.5


def test_regime_includes_spx_when_change_valid(monkeypatch):
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
                "indices": {"^GSPC": {"label": "S&P 500 (ES)", "change_1w_pct": 1.23}},
            },
        },
    )
    monkeypatch.setattr("services.term_structure.dashboard", lambda: {})
    monkeypatch.setattr("services.screener.sector_rotation", lambda: {"leaders": []})

    out = analysis.regime()
    spx = [s for s in out["signals"] if s["name"] == "S&P 500 (1w)"]
    assert len(spx) == 1
    assert spx[0]["reading"] == "+1.23%"
    assert spx[0]["leans"] == "risk-on"


def test_usable_index_bars_rejects_nan():
    from obb_layer.macro import _usable_index_bars

    rows = _bars(10)
    rows[5]["close"] = math.nan
    assert _usable_index_bars(rows) is True  # still enough finite closes

    rows = [{"date": "2026-01-01", "close": math.nan}] * 10
    assert _usable_index_bars(rows) is False
