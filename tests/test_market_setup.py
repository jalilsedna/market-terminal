"""Crypto/FX market setup (ROADMAP H7) — no network; FMP calls monkeypatched."""

from __future__ import annotations

import pytest


def test_fmp_symbol_normalization():
    from services.market_setup import _fmp_symbol

    assert _fmp_symbol("BTC-USD") == "BTCUSD"
    assert _fmp_symbol("EUR/USD") == "EURUSD"
    assert _fmp_symbol("eurusd") == "EURUSD"


def test_bias_and_conviction():
    from services.market_setup import _bias, _conviction

    assert _bias(3) == "long" and _bias(2) == "long"
    assert _bias(-2) == "short" and _bias(1) == "neutral"
    assert _conviction(3) == "high" and _conviction(2) == "moderate" and _conviction(1) == "low"


def test_market_setup_rejects_equity():
    from services import market_setup

    with pytest.raises(ValueError):
        market_setup.market_setup("equity", "AAPL")


def _patch_fmp(monkeypatch, *, price, ma50, ma200, rsi, adx, volume=None, avg=None,
               yhigh=None, ylow=None):
    import config
    from obb_layer import fmp

    monkeypatch.setenv("FMP_API_KEY", "k")
    config.get_settings.cache_clear()
    monkeypatch.setattr(fmp, "quote", lambda s: [{
        "price": price, "priceAvg50": ma50, "priceAvg200": ma200,
        "volume": volume, "avgVolume": avg, "yearHigh": yhigh, "yearLow": ylow,
    }])
    monkeypatch.setattr(fmp, "technical_indicator",
                        lambda s, ind="rsi", **k: [{ind: rsi if ind == "rsi" else adx}])


def test_market_setup_long(monkeypatch):
    import config
    from services import market_setup

    _patch_fmp(monkeypatch, price=110, ma50=100, ma200=90, rsi=72, adx=30,
               volume=3e6, avg=1e6, yhigh=120, ylow=60)
    try:
        out = market_setup.market_setup("crypto", "BTC-USD")
        assert out["errors"] is None
        assert out["components"]["trend"] == 2  # above both MAs
        assert out["components"]["momentum"] == 1  # rsi > 55
        assert out["bias"] == "long" and out["conviction"] == "high"
        assert out["in_play"] is True  # rvol 3x
        assert out["symbol"] == "BTC-USD"
    finally:
        config.get_settings.cache_clear()


def test_market_setup_degrades_on_quote_failure(monkeypatch):
    import config
    from obb_layer import fmp
    from services import market_setup

    monkeypatch.setenv("FMP_API_KEY", "k")
    config.get_settings.cache_clear()

    def boom(s):
        raise fmp.FmpError("quote: HTTP 403")

    monkeypatch.setattr(fmp, "quote", boom)
    monkeypatch.setattr(fmp, "technical_indicator", lambda s, ind="rsi", **k: [{ind: 25 if ind == "rsi" else 15}])
    try:
        out = market_setup.market_setup("forex", "EURUSD")
        assert out["errors"] and "quote" in out["errors"]  # surfaced, not crashed
        assert out["components"]["trend"] == 0  # no price → trend unknown
        assert out["components"]["momentum"] == -1  # rsi 25 still votes
    finally:
        config.get_settings.cache_clear()


def test_screen_ranks_and_isolates_errors(monkeypatch):
    import config
    from services import market_setup

    monkeypatch.setenv("FMP_API_KEY", "k")
    config.get_settings.cache_clear()

    def fake(asset, symbol):
        if symbol == "BAD":
            raise RuntimeError("boom")
        table = {"AAA": 3, "BBB": 0, "CCC": -3}
        return {"symbol": symbol, "asset": asset, "enabled": True,
                "bias": market_setup._bias(table[symbol]), "score": table[symbol],
                "components": {"trend": 0, "momentum": 0}}

    monkeypatch.setattr(market_setup, "market_setup", fake)
    try:
        out = market_setup.screen("crypto", symbols=["AAA", "BBB", "CCC", "BAD"])
        assert out["universe"] == "explicit" and out["count"] == 4
        order = [r["symbol"] for r in out["ranked"]]
        assert order[0] == "AAA"  # long first
        assert order[-1] == "BAD"  # error sinks to bottom
    finally:
        config.get_settings.cache_clear()
