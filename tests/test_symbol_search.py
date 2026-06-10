"""Symbol autocomplete search — no OpenBB/network."""

from __future__ import annotations

from services import symbol_search as ss


def test_forex_filters_by_prefix():
    hits = ss.search("forex", "EUR")
    syms = [h["symbol"] for h in hits]
    assert "EURUSD" in syms
    assert "EURGBP" in syms
    assert all(s.startswith("EUR") or "EUR" in s for s in syms)


def test_crypto_btc_prefix():
    hits = ss.search("crypto", "BT")
    assert any(h["symbol"] == "BTC-USD" for h in hits)


def test_futures_gc():
    hits = ss.search("futures", "GC")
    assert any(h["symbol"] == "GC=F" for h in hits)


def test_equity_without_alpaca_returns_empty(no_auth_env):
    assert ss.search("equity", "AAPL") == []
