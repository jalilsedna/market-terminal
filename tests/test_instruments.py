"""Unified instrument registry — no OpenBB, CI-gated."""

from __future__ import annotations

import pytest


@pytest.fixture
def reg(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "terminal.db"))
    import config

    config.get_settings.cache_clear()
    from services import instruments

    yield instruments
    config.get_settings.cache_clear()


def test_starts_empty(reg):
    assert reg.list_all() == []


def test_ensure_adds_when_missing(reg):
    inst = reg.ensure("equity", "CBRL")
    assert inst.id == "equity:CBRL"
    assert reg.resolve("CBRL").symbol == "CBRL"
    # Idempotent — returns existing row.
    again = reg.ensure("equity", "CBRL")
    assert again.id == inst.id
    assert len(reg.list_all()) == 1


def test_add_resolve_remove(reg):
    inst = reg.add("crypto", "BTC-USD", label="Bitcoin")
    assert inst.id == "crypto:BTC-USD"
    assert reg.resolve("crypto:BTC-USD").symbol == "BTC-USD"
    assert reg.resolve("BTC-USD").id == "crypto:BTC-USD"
    assert reg.remove("crypto:BTC-USD") is True
    assert reg.list_all() == []


def test_futures_template_enriches_meta(reg):
    inst = reg.add("futures", "GC=F")
    assert inst.meta.get("cot_code") == "088691"
    assert inst.code == "GC"
    assert inst.capabilities()["cot"] is True


def test_non_template_futures_resolves_cot_from_root(reg):
    # CL (crude) isn't a template, but it's in the CFTC code map → COT works.
    inst = reg.add("futures", "CL=F")
    assert inst.meta.get("cot_code") in (None, "067651")  # filled on add OR resolved
    assert inst.cot_code == "067651"
    assert inst.capabilities()["cot"] is True


def test_unmapped_futures_has_no_cot(reg):
    inst = reg.add("futures", "XYZ=F")
    assert inst.cot_code is None
    assert inst.capabilities()["cot"] is False


def test_cot_code_for_helper():
    from obb_layer.symbols import cot_code_for

    assert cot_code_for("CL") == "067651"
    assert cot_code_for("ES") == "13874A"
    assert cot_code_for("cl=f") == "067651"
    assert cot_code_for("NOPE") is None
    assert cot_code_for(None) is None


def test_equity_no_cot(reg):
    inst = reg.add("equity", "AAPL")
    assert inst.capabilities()["cot"] is False
    assert inst.capabilities()["fundamentals"] is True


def test_seed_defaults_on_empty_then_noop(reg):
    n = reg.seed_defaults()
    assert n == len(reg.DEFAULT_SEED) + len(reg.DEFAULT_FOREX_SEED)
    codes = {i.code for i in reg.list_all()}
    assert {"6E", "6B", "GC", "NQ", "YM"} <= codes
    # Spot forex + metals (the IBKR book) are seeded as `forex` instruments.
    forex_syms = {i.symbol for i in reg.list_all() if i.asset == "forex"}
    assert {"EURUSD", "USDJPY", "XAUUSD", "XAGUSD"} <= forex_syms
    # Idempotent: a second call seeds nothing because the registry is non-empty.
    assert reg.seed_defaults() == 0


def test_seed_skipped_when_user_has_instruments(reg):
    reg.add("crypto", "BTC-USD")
    assert reg.seed_defaults() == 0
    assert {i.id for i in reg.list_all()} == {"crypto:BTC-USD"}
