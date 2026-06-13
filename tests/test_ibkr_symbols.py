"""Research-symbol → IBKR contract map (ROADMAP A10) — no network."""

from __future__ import annotations

from obb_layer.ibkr_symbols import ibkr_contract


def test_spot_fx_dots_the_pair():
    c = ibkr_contract("EURUSD", "forex")
    assert c["contract"] == "EUR.USD"
    assert c["venue"] == "IDEALPRO"
    assert c["sec_type"] == "CASH"
    assert c["research_symbol"] == "EURUSD"


def test_spot_metal_is_commodity():
    c = ibkr_contract("XAUUSD", "forex")
    assert c["contract"] == "XAU.USD"
    assert c["venue"] == "IDEALPRO"
    assert c["sec_type"] == "CMDTY"


def test_futures_front_contract():
    assert ibkr_contract("GC=F", "futures")["contract"] == "GC"
    assert ibkr_contract("GC=F", "futures")["venue"] == "COMEX"
    # FX futures map to the cleaner IDEALPRO spot pair.
    assert ibkr_contract("6E=F", "futures")["contract"] == "EUR.USD"


def test_equity_uses_plain_ticker_smart():
    c = ibkr_contract("AAPL", "equity")
    assert c["contract"] == "AAPL"
    assert c["venue"] == "SMART"
    assert c["sec_type"] == "STK"


def test_crypto_has_no_natural_ibkr_mapping():
    assert ibkr_contract("BTC-USD", "crypto") is None


def test_six_char_alpha_inferred_as_fx_without_asset():
    assert ibkr_contract("USDJPY")["contract"] == "USD.JPY"


def test_empty_symbol_is_none():
    assert ibkr_contract("", "forex") is None
