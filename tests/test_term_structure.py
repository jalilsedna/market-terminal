"""Term structure helpers — no network in unit tests."""

from __future__ import annotations

from datetime import date

from obb_layer.fmp_curve import expiration_from_trade_month
from services import term_structure as svc


def test_expiration_from_trade_month():
    assert expiration_from_trade_month("Jun", ref=date(2026, 3, 1)) == "2026-06"
    assert expiration_from_trade_month("Dec", ref=date(2026, 6, 1)) == "2026-12"


def test_curve_classify_contango(monkeypatch):
    monkeypatch.setattr(svc, "_UNAVAILABLE", set())  # treat GC as available for the test
    monkeypatch.setattr(
        "obb_layer.term_structure.futures_curve",
        lambda symbol, provider="fmp", date=None: [
            {"expiration": "2026-06", "price": 100.0},
            {"expiration": "2026-12", "price": 105.0},
        ],
    )
    result = svc.curve("GC")
    assert result["structure"] == "contango"
    assert result["front_price"] == 100.0
    assert result["back_price"] == 105.0
    assert result["code"] == "GC"
    assert result["provider"] == "fmp"


def test_curve_classify_backwardation(monkeypatch):
    monkeypatch.setattr(svc, "_UNAVAILABLE", set())
    monkeypatch.setattr(
        "obb_layer.term_structure.futures_curve",
        lambda symbol, provider="fmp", date=None: [
            {"expiration": "2026-06", "price": 110.0},
            {"expiration": "2026-12", "price": 100.0},
        ],
    )
    result = svc.curve("CL")
    assert result["structure"] == "backwardation"


def test_commodity_curves_unavailable_by_default():
    """GC/CL/NG have no live futures source → clean unavailable, not an error."""
    import pytest

    for code in ("GC", "CL", "NG"):
        with pytest.raises(svc.CurveUnavailable):
            svc.curve(code)


def test_dashboard_marks_commodities_unavailable_keeps_vix(monkeypatch):
    monkeypatch.setattr(
        "obb_layer.term_structure.futures_curve",
        lambda symbol, provider="cboe", date=None: [
            {"expiration": "2026-06", "price": 19.0},
            {"expiration": "2026-12", "price": 22.0},
        ],
    )
    d = svc.dashboard()
    for code in ("GC", "CL", "NG"):
        assert d[code]["ok"] is True
        assert d[code]["unavailable"] is True
        assert "note" in d[code]
    assert d["VIX"]["ok"] is True
    assert d["VIX"].get("unavailable") is None
    assert d["VIX"]["structure"] == "contango"


def test_fmp_curve_builds_from_list_and_batch(monkeypatch):
    from obb_layer import fmp
    from obb_layer.fmp_curve import futures_curve

    monkeypatch.setattr(
        fmp,
        "commodities_list",
        lambda: [
            {"symbol": "GCM26USD", "name": "Gold Futures", "tradeMonth": "Jun"},
            {"symbol": "GCZ26USD", "name": "Gold Futures", "tradeMonth": "Dec"},
        ],
    )
    monkeypatch.setattr(
        fmp,
        "batch_commodity_quotes",
        lambda: [
            {"symbol": "GCM26USD", "price": 2400.0},
            {"symbol": "GCZ26USD", "price": 2450.0},
        ],
    )
    points = futures_curve("GC")
    assert len(points) == 2
    by_exp = {p["expiration"]: p["price"] for p in points}
    assert by_exp["2026-06"] == 2400.0
    assert by_exp["2026-12"] == 2450.0
