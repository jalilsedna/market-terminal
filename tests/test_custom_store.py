"""Custom-watchlist store — SQLite-backed CRUD (no OpenBB, runs in CI)."""

from __future__ import annotations

import pytest


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "terminal.db"))
    import config

    config.get_settings.cache_clear()
    from services import custom_store

    yield custom_store
    config.get_settings.cache_clear()
    config.get_settings.cache_clear()


def test_starts_empty(store):
    assert store.list_items() == []


def test_add_list_remove(store):
    e = store.add("crypto", "BTC-USD")
    assert e["id"] == "crypto:BTC-USD"
    assert e["asset"] == "crypto"
    assert e["symbol"] == "BTC-USD"
    assert e["label"] == "BTC-USD"
    assert e["meta"] == {}
    store.add("equity", "AAPL", label="Apple")
    ids = [i["id"] for i in store.list_items()]
    assert ids == ["crypto:BTC-USD", "equity:AAPL"]
    assert store.remove("crypto:BTC-USD") is True
    assert [i["id"] for i in store.list_items()] == ["equity:AAPL"]
    assert store.remove("nope:nope") is False


def test_add_is_idempotent(store):
    store.add("forex", "EURUSD")
    store.add("forex", "EURUSD")
    assert len(store.list_items()) == 1


def test_add_validates(store):
    with pytest.raises(ValueError):
        store.add("bogus", "X")
    with pytest.raises(ValueError):
        store.add("crypto", "  ")


def test_persists_across_calls(store):
    store.add("etf", "SPY")
    # a fresh read (new list_items call) sees the persisted file
    assert any(i["symbol"] == "SPY" for i in store.list_items())
