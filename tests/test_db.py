"""SQLite persistence layer (ROADMAP C2) — kv, watchlist, history. No OpenBB."""

from __future__ import annotations

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "terminal.db"))
    import config

    config.get_settings.cache_clear()
    from app import db as _db

    yield _db
    config.get_settings.cache_clear()


def test_kv_roundtrip(db):
    assert db.kv_get("missing", "fallback") == "fallback"
    db.kv_set("k", {"a": 1, "b": [2, 3]})
    assert db.kv_get("k") == {"a": 1, "b": [2, 3]}
    db.kv_set("k", "overwritten")
    assert db.kv_get("k") == "overwritten"


def test_watchlist_crud(db):
    assert db.watchlist_list() == []
    db.watchlist_add("crypto:BTC-USD", "crypto", "BTC-USD", "BTC-USD")
    db.watchlist_add("equity:AAPL", "equity", "AAPL", "Apple")
    assert [i["id"] for i in db.watchlist_list()] == ["crypto:BTC-USD", "equity:AAPL"]
    # idempotent on id
    db.watchlist_add("crypto:BTC-USD", "crypto", "BTC-USD", "dup")
    assert len(db.watchlist_list()) == 2
    assert db.watchlist_remove("crypto:BTC-USD") is True
    assert db.watchlist_remove("nope") is False
    assert [i["id"] for i in db.watchlist_list()] == ["equity:AAPL"]


def test_persists_across_connections(db):
    # each call opens its own connection — data must survive
    db.watchlist_add("etf:SPY", "etf", "SPY", "SPY")
    assert any(i["symbol"] == "SPY" for i in db.watchlist_list())


def test_history_snapshots(db):
    db.record_snapshot("vol:GC", {"vol": 0.18}, ts="2026-01-01T00:00:00+00:00")
    db.record_snapshot("vol:GC", {"vol": 0.20}, ts="2026-01-02T00:00:00+00:00")
    db.record_snapshot("vol:NQ", {"vol": 0.30}, ts="2026-01-02T00:00:00+00:00")
    hist = db.history("vol:GC")
    assert [h["value"]["vol"] for h in hist] == [0.20, 0.18]  # newest first
    assert len(db.history("vol:NQ")) == 1
    assert db.history("vol:GC", limit=1) == [
        {"ts": "2026-01-02T00:00:00+00:00", "value": {"vol": 0.20}}
    ]
