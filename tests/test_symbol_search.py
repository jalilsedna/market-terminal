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


def test_equity_curated_without_alpaca(no_auth_env):
    hits = ss.search("equity", "MSF")
    assert any(h["symbol"] == "MSFT" for h in hits)


def test_etf_curated_without_alpaca(no_auth_env):
    hits = ss.search("etf", "QQ")
    assert any(h["symbol"] == "QQQ" for h in hits)
    assert all(h["asset"] == "etf" for h in hits)


def test_equity_excludes_etfs_from_curated(no_auth_env):
    hits = ss.search("equity", "SPY")
    assert not any(h["symbol"] == "SPY" for h in hits)
