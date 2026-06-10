"""Per-provider symbol mapping (ROADMAP B-next) — pure, no OpenBB."""

from __future__ import annotations

from obb_layer.symbol_map import map_symbol


def test_crypto_mapping_per_provider():
    assert map_symbol("crypto", "BTC-USD", "polygon") == "X:BTCUSD"
    assert map_symbol("crypto", "BTC-USD", "tiingo") == "btcusd"
    assert map_symbol("crypto", "BTC-USD", "fmp") == "BTCUSD"
    # case-insensitive input, USDT quote
    assert map_symbol("crypto", "eth-usdt", "polygon") == "X:ETHUSDT"


def test_forex_mapping_per_provider():
    assert map_symbol("forex", "EURUSD", "polygon") == "C:EURUSD"
    assert map_symbol("forex", "EURUSD", "tiingo") == "eurusd"
    assert map_symbol("forex", "EURUSD", "fmp") == "EURUSD"
    # tolerates =X / slash forms
    assert map_symbol("forex", "EURUSD=X", "polygon") == "C:EURUSD"
    assert map_symbol("forex", "GBP/USD", "polygon") == "C:GBPUSD"


def test_unmapped_provider_returns_none():
    assert map_symbol("crypto", "BTC-USD", "mystery") is None
    assert map_symbol("forex", "EURUSD", "mystery") is None


def test_unparseable_symbol_returns_none():
    assert map_symbol("crypto", "BTCUSD", "polygon") is None   # no dash → can't split
    assert map_symbol("forex", "EUR", "polygon") is None       # not 6 chars


def test_equity_and_etf_pass_through():
    assert map_symbol("equity", "AAPL", "tiingo") == "AAPL"
    assert map_symbol("etf", "SPY", "polygon") == "SPY"
    assert map_symbol("", "AAPL", "fmp") == "AAPL"
