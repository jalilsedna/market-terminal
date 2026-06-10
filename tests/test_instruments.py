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


def test_equity_no_cot(reg):
    inst = reg.add("equity", "AAPL")
    assert inst.capabilities()["cot"] is False
    assert inst.capabilities()["fundamentals"] is True
