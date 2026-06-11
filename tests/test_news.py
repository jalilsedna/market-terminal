"""News feed — world-wire vs proxy fallback + tagging (no OpenBB/network)."""

from __future__ import annotations

import pytest


@pytest.fixture
def clear_settings(monkeypatch):
    for k in ("FMP_API_KEY", "BENZINGA_API_KEY", "TIINGO_API_KEY", "INTRINIO_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    import config

    config.get_settings.cache_clear()
    yield monkeypatch
    config.get_settings.cache_clear()


def test_world_provider_priority(clear_settings):
    import config
    from services import news as svc

    assert svc._world_provider() is None  # no keys → proxy feed
    clear_settings.setenv("TIINGO_API_KEY", "t")
    config.get_settings.cache_clear()
    assert svc._world_provider() == "tiingo"
    clear_settings.setenv("FMP_API_KEY", "f")  # fmp outranks tiingo
    config.get_settings.cache_clear()
    assert svc._world_provider() == "fmp"


def test_world_headline_tags_macro_and_instrument(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "terminal.db"))
    import config

    config.get_settings.cache_clear()
    from services import instruments as reg
    from services import news as svc

    reg.add("futures", "GC=F")
    h = svc._world_headline({
        "title": "Gold rallies as the Fed signals a rate cut",
        "text": "bullion up on dovish FOMC", "url": "u1", "date": "2026-06-09", "site": "wire",
    })
    assert "macro" in h["tags"] and "GC" in h["tags"]
    assert h["source"] == "wire"
    config.get_settings.cache_clear()


def test_feed_uses_world_wire_when_key_set(clear_settings, monkeypatch):
    import config
    from obb_layer import news as obb_news
    from services import news as svc

    clear_settings.setenv("FMP_API_KEY", "f")
    config.get_settings.cache_clear()

    def fake_world(provider="fmp", limit=100):
        assert provider == "fmp"
        return [
            {"title": "Dollar climbs", "text": "DXY up", "url": "a", "date": "2026-06-09"},
            {"title": "Dollar climbs", "text": "dup", "url": "a", "date": "2026-06-09"},  # dupe
            {"title": "Nasdaq slips", "text": "tech stocks down", "url": "b", "date": "2026-06-08"},
        ]

    monkeypatch.setattr(obb_news, "world_news", fake_world)
    out = svc.feed(limit=10)
    assert out["filter"] == "world" and out["provider"] == "fmp"
    assert out["count"] == 2  # deduped by url
    assert out["headlines"][0]["title"] == "Dollar climbs"  # newest first


def test_feed_falls_back_to_proxy_without_key(clear_settings, monkeypatch, tmp_path):
    import config
    from obb_layer import news as obb_news
    from services import instruments as reg
    from services import news as svc

    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    config.get_settings.cache_clear()
    reg.add("equity", "AAPL")

    def fake_company(symbol, provider="fmp", limit=50):
        return [{"title": f"{symbol} news", "url": f"u-{symbol}", "date": "2026-06-09"}]

    monkeypatch.setattr(obb_news, "company_news", fake_company)
    out = svc.feed(limit=10)
    assert out["filter"] == "registry"
    assert out["count"] >= 1


def test_crypto_news_ticker_uses_fmp_format(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    import config

    config.get_settings.cache_clear()
    from services import instruments as reg
    from services import news as svc

    inst = reg.add("crypto", "BTC-USD")
    assert svc._news_ticker(inst) == "BTCUSD"
    config.get_settings.cache_clear()


def test_crypto_feed_falls_back_to_world_keywords(clear_settings, monkeypatch, tmp_path):
    import config
    from obb_layer import news as obb_news
    from services import instruments as reg
    from services import news as svc

    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    clear_settings.setenv("FMP_API_KEY", "f")
    config.get_settings.cache_clear()
    inst = reg.add("crypto", "BTC-USD")
    tag = inst.code or inst.id

    def fake_company(symbol, provider="fmp", limit=50):
        assert symbol == "BTCUSD"
        return []

    def fake_world(provider="fmp", limit=100):
        return [
            {"title": "Bitcoin rallies on ETF inflows", "text": "btc up", "url": "u-btc", "date": "2026-06-11"},
            {"title": "Oil slips", "text": "crude down", "url": "u-oil", "date": "2026-06-10"},
        ]

    monkeypatch.setattr(obb_news, "company_news", fake_company)
    monkeypatch.setattr(obb_news, "world_news", fake_world)
    out = svc.feed(limit=10, instrument=inst.id)
    assert out["count"] == 1
    assert "Bitcoin" in out["headlines"][0]["title"]
    config.get_settings.cache_clear()


def test_feed_falls_back_when_world_wire_errors(clear_settings, monkeypatch, tmp_path):
    import config
    from obb_layer import news as obb_news
    from services import instruments as reg
    from services import news as svc

    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    clear_settings.setenv("FMP_API_KEY", "f")
    config.get_settings.cache_clear()
    reg.add("equity", "AAPL")

    def boom(provider="fmp", limit=100):
        raise RuntimeError("402 paywalled")

    def fake_company(symbol, provider="fmp", limit=50):
        return [{"title": f"{symbol} news", "url": f"u-{symbol}", "date": "2026-06-09"}]

    monkeypatch.setattr(obb_news, "world_news", boom)
    monkeypatch.setattr(obb_news, "company_news", fake_company)
    out = svc.feed(limit=10)
    assert out["filter"] == "registry"  # gracefully degraded to proxy
