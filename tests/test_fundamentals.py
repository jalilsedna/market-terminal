"""FMP fundamentals (ROADMAP H, Phase 1) — composition + client (no network)."""

from __future__ import annotations

import httpx
import pytest


def test_pick_first_present():
    from services.fundamentals import _pick

    assert _pick({"a": 1, "b": 2}, "x", "a") == 1
    assert _pick({"a": None, "b": 2}, "a", "b") == 2
    assert _pick({}, "a") is None


def test_dashboard_composition(monkeypatch):
    from obb_layer import fmp
    from services import fundamentals as f

    monkeypatch.setattr(fmp, "profile", lambda s: [{
        "companyName": "Apple", "sector": "Tech", "industry": "Devices",
        "exchangeShortName": "NASDAQ", "price": 190, "marketCap": 3e12, "beta": 1.2,
        "description": "iPhone maker",
    }])
    monkeypatch.setattr(fmp, "ratios", lambda s, **k: [{
        "priceEarningsRatio": 30, "priceToSalesRatio": 8, "priceToBookRatio": 45,
        "dividendYield": 0.005, "returnOnEquity": 1.5, "netProfitMargin": 0.25,
        "debtEquityRatio": 1.5, "currentRatio": 1.1,
    }])
    monkeypatch.setattr(fmp, "key_metrics", lambda s, **k: [{
        "evToEBITDA": 22, "freeCashFlowYield": 0.03, "roic": 0.5,
    }])
    monkeypatch.setattr(fmp, "financial_scores", lambda s: [{"piotroskiScore": 8, "altmanZScore": 7.2}])
    monkeypatch.setattr(fmp, "income_growth", lambda s, **k: [{
        "growthRevenue": 0.08, "growthEPS": 0.12, "growthNetIncome": 0.1, "date": "2025",
    }])
    monkeypatch.setattr(fmp, "peers", lambda s: [{"symbol": "AAPL", "peersList": ["MSFT", "GOOGL"]}])
    monkeypatch.setattr(fmp, "revenue_geo", lambda s: [{"date": "2025", "Americas": 2e11, "Europe": 1e11}])
    monkeypatch.setattr(fmp, "revenue_product", lambda s: [])
    # H2 endpoints
    monkeypatch.setattr(fmp, "dcf", lambda s: [{"dcf": 220.0}])
    monkeypatch.setattr(fmp, "price_target_consensus", lambda s: [{"targetConsensus": 209.0}])
    monkeypatch.setattr(fmp, "ratings_snapshot", lambda s: [{"rating": "Buy"}])
    monkeypatch.setattr(fmp, "earnings", lambda s, **k: [])
    monkeypatch.setattr(fmp, "dividends", lambda s, **k: [])

    d = f.dashboard("aapl")
    assert d["symbol"] == "AAPL"
    assert d["profile"]["name"] == "Apple" and d["profile"]["sector"] == "Tech"
    assert d["valuation"]["pe"] == 30 and d["valuation"]["ev_ebitda"] == 22
    assert d["valuation"]["fcf_yield"] == 0.03
    assert d["quality"]["piotroski"] == 8 and d["quality"]["altman_z"] == 7.2
    assert d["quality"]["roe"] == 1.5
    assert d["growth"]["revenue"] == 0.08 and d["growth"]["eps"] == 0.12
    assert d["peers"] == ["MSFT", "GOOGL"]
    assert d["segmentation"]["geographic"] == {"Americas": 2e11, "Europe": 1e11}
    assert d["errors"] is None


def test_stable_field_names_resolve(monkeypatch):
    """FMP `stable` uses priceToEarningsRatio / debtToEquityRatio (verified live)."""
    from obb_layer import fmp
    from services import fundamentals as f

    monkeypatch.setattr(fmp, "profile", lambda s: [{"companyName": "Apple"}])
    monkeypatch.setattr(fmp, "ratios", lambda s, **k: [{
        "priceToEarningsRatio": 33.5, "debtToEquityRatio": 1.87,
    }])
    for name in ("key_metrics", "income_growth"):
        monkeypatch.setattr(fmp, name, lambda s, **k: [])
    monkeypatch.setattr(fmp, "financial_scores", lambda s: [])
    monkeypatch.setattr(fmp, "peers", lambda s: [])
    monkeypatch.setattr(fmp, "revenue_geo", lambda s: None)
    monkeypatch.setattr(fmp, "revenue_product", lambda s: None)

    d = f.dashboard("AAPL")
    assert d["valuation"]["pe"] == 33.5
    assert d["quality"]["debt_to_equity"] == 1.87


def test_dashboard_is_fault_tolerant(monkeypatch):
    from obb_layer import fmp
    from services import fundamentals as f

    def boom(*a, **k):
        raise fmp.FmpError("ratios: HTTP 403")

    monkeypatch.setattr(fmp, "profile", lambda s: [{"companyName": "X"}])
    monkeypatch.setattr(fmp, "ratios", boom)  # one gated endpoint
    for name in ("key_metrics", "income_growth"):
        monkeypatch.setattr(fmp, name, lambda s, **k: [])
    monkeypatch.setattr(fmp, "financial_scores", lambda s: [])
    monkeypatch.setattr(fmp, "peers", lambda s: [])
    monkeypatch.setattr(fmp, "revenue_geo", lambda s: None)
    monkeypatch.setattr(fmp, "revenue_product", lambda s: None)

    d = f.dashboard("X")
    assert d["profile"]["name"] == "X"  # view still composes
    assert "ratios" in (d["errors"] or {})  # the gated block is reported


def test_dcf_and_analyst_extraction():
    from services.fundamentals import _analyst, _dcf

    dcf = _dcf({"dcf": 220.0}, price=190.0)
    assert dcf["fair_value"] == 220.0
    assert round(dcf["gap"], 4) == round((220 - 190) / 190, 4)  # undervalued

    an = _analyst({"targetConsensus": 209.0}, {"rating": "Buy"}, price=190.0)
    assert an["target"] == 209.0 and an["rating"] == "Buy"
    assert round(an["upside"], 4) == round((209 - 190) / 190, 4)


def test_next_earnings_picks_future_and_last():
    from datetime import UTC, datetime, timedelta

    from services.fundamentals import _next_earnings

    today = datetime.now(UTC).date()
    rows = [
        {"date": (today - timedelta(days=80)).isoformat(), "epsActual": 1.2, "epsEstimated": 1.1},
        {"date": (today + timedelta(days=9)).isoformat()},
        {"date": (today + timedelta(days=100)).isoformat()},
    ]
    out = _next_earnings(rows)
    assert out["days_away"] == 9
    assert out["last_eps_actual"] == 1.2


def test_median_and_pe_series():
    from services.fundamentals import _median, _pe_series

    assert _median([10, 20, 30]) == 20
    assert _median([10, 20, 30, 40]) == 25
    assert _median([]) is None
    series = [{"priceToEarningsRatio": 30}, {"priceEarningsRatio": 28}, {"peRatio": -5}, {}]
    assert _pe_series(series) == [30, 28]  # negative/missing P/E dropped


def test_read_valuation_relative_primary():
    """Premium compounder near its own 5y P/E median reads 'fair', not 'expensive',
    even when a naive DCF is deeply negative (B fix)."""
    from services.fundamentals import _read

    out = _read(
        valuation={"pe": 33.0, "pe_median": 30.0}, quality={"piotroski": 9},
        growth={"revenue": 0.06}, dcf={"gap": -0.47},  # DCF says very expensive
        analyst={"upside": 0.13}, earnings={"days_away": 50},
    )
    assert out["labels"]["valuation"] == "fair"  # P/E 33 vs med 30 → rel 1.1 → fair
    assert "DCF -47%" in out["verdict"]  # DCF still shown as context


def test_read_valuation_relative_cheap_and_expensive():
    from services.fundamentals import _read

    cheap = _read({"pe": 12.0, "pe_median": 20.0}, {}, {}, {}, {}, {})
    assert cheap["labels"]["valuation"] == "cheap"
    rich = _read({"pe": 40.0, "pe_median": 20.0}, {}, {}, {}, {}, {})
    assert rich["labels"]["valuation"] == "expensive"


def test_read_falls_back_to_dcf_without_pe_history():
    from services.fundamentals import _read

    out = _read({"pe": None, "pe_median": None}, {}, {}, {"gap": 0.22}, {}, {})
    assert out["labels"]["valuation"] == "cheap"  # DCF fallback when no P/E history


def test_read_verdict_and_flags():
    from services.fundamentals import _read

    out = _read(
        valuation={}, quality={"piotroski": 8, "altman_z": 6.0},
        growth={"revenue": 0.08}, dcf={"gap": 0.22},
        analyst={"upside": 0.12}, earnings={"days_away": 9},
    )
    assert "cheap" in out["verdict"] and "strong quality" in out["verdict"]
    assert "growing" in out["verdict"] and "analysts +12%" in out["verdict"]
    assert any("event risk" in f for f in out["flags"])  # earnings in 9d
    assert out["labels"]["valuation"] == "cheap"


def test_read_distress_flag_and_insufficient():
    from services.fundamentals import _read

    distress = _read({}, {"piotroski": 2, "altman_z": 1.2}, {}, {}, {}, {})
    assert any("distress" in f for f in distress["flags"])
    assert "weak quality" in distress["verdict"]

    empty = _read({}, {}, {}, {}, {}, {})
    assert empty["verdict"] == "insufficient fundamental data"


def test_client_disabled_without_key(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    import config

    config.get_settings.cache_clear()
    from obb_layer import fmp

    with pytest.raises(fmp.FmpDisabled):
        fmp._get("profile", symbol="AAPL")
    config.get_settings.cache_clear()


def test_client_sanitizes_error_no_key_leak(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "sekret-key-123")
    import config

    config.get_settings.cache_clear()
    from obb_layer import fmp

    def fake_get(url, params=None, timeout=None):
        return httpx.Response(403, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    try:
        with pytest.raises(fmp.FmpError) as ei:
            fmp._get("profile", symbol="AAPL")
        msg = str(ei.value)
        assert "403" in msg
        assert "sekret-key-123" not in msg  # the apikey must never appear in errors
    finally:
        config.get_settings.cache_clear()
