"""Fundamental equity screener (ROADMAP H4) — filter mapping + normalize, no network."""

from __future__ import annotations


def test_screen_maps_filters_and_normalizes(monkeypatch):
    import config
    from obb_layer import fmp
    from services import screener

    monkeypatch.setenv("FMP_API_KEY", "k")
    config.get_settings.cache_clear()

    captured = {}

    def fake_screener(**filters):
        captured.update(filters)
        return [
            {"symbol": "AAPL", "companyName": "Apple Inc.", "price": 291.5,
             "marketCap": 4.3e12, "beta": 1.2, "lastAnnualDividend": 1.0,
             "volume": 5e7, "sector": "Technology", "industry": "Consumer Electronics",
             "exchangeShortName": "NASDAQ"},
            {"symbol": "TINY", "companyName": "Tiny Co", "marketCap": 1e9, "price": 5.0},
        ]

    monkeypatch.setattr(fmp, "company_screener", fake_screener)
    try:
        out = screener.run_screen(sector="Technology", mktcap_min=1e9, beta_max=1.5, limit=10)
        # friendly params mapped to FMP names
        assert captured["sector"] == "Technology"
        assert captured["marketCapMoreThan"] == 1e9
        assert captured["betaLowerThan"] == 1.5
        assert captured["isActivelyTrading"] is True
        # normalized + sorted by market cap (AAPL first)
        assert out["enabled"] is True and out["count"] == 2
        assert out["results"][0]["symbol"] == "AAPL"
        assert out["results"][0]["name"] == "Apple Inc."
        assert out["results"][0]["exchange"] == "NASDAQ"
        assert out["criteria"]["sector"] == "Technology"
    finally:
        config.get_settings.cache_clear()


def test_screen_degrades_on_gated_endpoint(monkeypatch):
    import config
    from obb_layer import fmp
    from services import screener

    monkeypatch.setenv("FMP_API_KEY", "k")
    config.get_settings.cache_clear()

    def boom(**f):
        raise fmp.FmpError("company-screener: HTTP 402")

    monkeypatch.setattr(fmp, "company_screener", boom)
    try:
        out = screener.run_screen(sector="Energy")
        assert out["enabled"] is True and out["count"] == 0
        assert "402" in out["error"]  # surfaced, not raised
    finally:
        config.get_settings.cache_clear()


def test_screen_no_key(monkeypatch):
    import config
    from services import screener

    monkeypatch.delenv("FMP_API_KEY", raising=False)
    config.get_settings.cache_clear()
    try:
        out = screener.run_screen(sector="Energy")
        assert out["enabled"] is False and "FMP" in out["error"]
    finally:
        config.get_settings.cache_clear()
