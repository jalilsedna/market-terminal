"""Chart tab — TradingView symbol map + /chart/symbols (no OpenBB, runs in CI)."""

from __future__ import annotations

import re

import pytest


def test_template_tv_symbols_are_valid():
    from obb_layer.symbols import INSTRUMENT_TEMPLATES

    pat = re.compile(r"^[A-Z_]+:[A-Z0-9]+!$")
    for code, inst in INSTRUMENT_TEMPLATES.items():
        assert inst.tv_symbol, f"{code} missing tv_symbol"
        assert pat.match(inst.tv_symbol), f"{code} tv_symbol '{inst.tv_symbol}' invalid"


def test_chart_symbols_endpoint_empty_registry(store):
    from app.routers.chart import chart_symbols

    env = chart_symbols()
    assert env.ok is True
    assert env.provider == "tradingview"
    assert env.data["picks"] == []


def test_chart_symbols_from_registry(store):
    from app.routers.chart import chart_symbols

    store.add("futures", "GC=F", label="Gold", meta={"tv_symbol": "COMEX:GC1!", "code": "GC"})
    env = chart_symbols()
    picks = env.data["picks"]
    assert len(picks) == 1
    assert picks[0]["tv_symbol"] == "COMEX:GC1!"


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "terminal.db"))
    import config

    config.get_settings.cache_clear()
    from services import custom_store

    yield custom_store
    config.get_settings.cache_clear()
