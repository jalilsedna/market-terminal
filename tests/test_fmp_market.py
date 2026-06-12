"""FMP market symbol mapping — no network."""

from __future__ import annotations

from obb_layer.fmp_market import (
    crypto_fmp_symbol,
    fx_fmp_symbol,
    resolve_fmp_symbol,
)


def test_futures_continuation_map():
    assert resolve_fmp_symbol("GC=F") == "GCUSD"
    assert resolve_fmp_symbol("NQ=F") == "^NDX"


def test_fx_proxy_strips_suffix():
    assert resolve_fmp_symbol("EURUSD=X") == "EURUSD"


def test_currency_futures_mapped_to_fmp_pairs():
    # 6A=F (AUD) used to resolve to the bogus '6AUSD'; now an explicit FX pair.
    assert resolve_fmp_symbol("6A=F") == "AUDUSD"
    assert resolve_fmp_symbol("6E=F") == "EURUSD"


def test_crypto_symbol_resolves_to_fmp_pair():
    assert crypto_fmp_symbol("BTC-USD") == "BTCUSD"
    assert crypto_fmp_symbol("eth/usd") == "ETHUSD"
    assert crypto_fmp_symbol("SOLUSD") == "SOLUSD"


def test_fx_symbol_resolves_to_fmp_pair():
    assert fx_fmp_symbol("EURUSD") == "EURUSD"
    assert fx_fmp_symbol("gbp/usd") == "GBPUSD"
    assert fx_fmp_symbol("NZDUSD=X") == "NZDUSD"
