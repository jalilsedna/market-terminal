"""/doctor diagnostic — db.stats, cache.stats, report assembly (no OpenBB)."""

from __future__ import annotations

import pytest


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    import config

    config.get_settings.cache_clear()
    from app import db
    from cache import store
    from services import doctor

    store.clear()
    yield db, doctor, store
    config.get_settings.cache_clear()
    store.clear()


def test_db_stats_counts(env):
    db, _doctor, _store = env
    s0 = db.stats()
    assert s0["writable"] is True
    assert s0["counts"]["watchlist"] == 0
    db.watchlist_add("crypto:BTC-USD", "crypto", "BTC-USD", "BTC")
    db.record_snapshot("vol:GC", {"vol": 0.2})
    s1 = db.stats()
    assert s1["counts"]["watchlist"] == 1
    assert s1["counts"]["snapshots"] == 1
    assert s1["series"] == ["vol:GC"]


def test_cache_stats(env):
    _db, _doctor, store = env
    assert store.stats()["entries"] == 0
    store.get_or_set("eod", "ns.fn", {"a": 1}, lambda: [1, 2, 3])
    st = store.stats()
    assert st["entries"] == 1
    assert st["live"] == 1
    assert st["namespaces"] == ["ns.fn"]


def test_report_shape_and_checks(env):
    _db, doctor, _store = env
    rep = doctor.report(user="admin", role="admin")
    assert rep["auth"]["user"] == "admin"
    assert rep["healthy"] is True  # tmp DB is writable
    assert set(rep["providers"]) == {"configured", "eod_chain", "movers_configured"}
    names = {c["name"]: c["ok"] for c in rep["checks"]}
    # optional integrations unset in this env → advisory checks report not-ok
    assert names["fred configured"] is False
    assert names["movers configured"] is False
    # tmp DB_PATH is not the default cache/ path → persistence check passes
    assert names["database on a persistent volume"] is True
    assert names["database writable"] is True


def test_report_flags_default_db_path(env, monkeypatch):
    _db, doctor, _store = env
    monkeypatch.setenv("DB_PATH", "cache/data/terminal.db")
    import config

    config.get_settings.cache_clear()
    rep = doctor.report()
    names = {c["name"]: c["ok"] for c in rep["checks"]}
    assert names["database on a persistent volume"] is False  # warns on default path
