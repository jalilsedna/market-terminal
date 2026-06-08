"""Alert rules + evaluation (ROADMAP C5) — no OpenBB, runs in CI."""

from __future__ import annotations

import pytest


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    import config

    config.get_settings.cache_clear()
    from app import db
    from services import alerts

    yield db, alerts
    config.get_settings.cache_clear()


def test_add_rule_validates(env):
    _, alerts = env
    # bad metric
    with pytest.raises(alerts.RuleError):
        alerts.add_rule("vol:GC", "bogus", ">", 1)
    # numeric op on a numeric metric is required
    with pytest.raises(alerts.RuleError):
        alerts.add_rule("vol:GC", "percentile", "==", 90)
    # non-numeric threshold for a numeric metric
    with pytest.raises(alerts.RuleError):
        alerts.add_rule("vol:GC", "percentile", ">", "high")
    # categorical needs == / !=
    with pytest.raises(alerts.RuleError):
        alerts.add_rule("vol:GC", "regime", ">", "stressed")
    # series required
    with pytest.raises(alerts.RuleError):
        alerts.add_rule("", "regime", "==", "stressed")


def test_add_and_list_roundtrip(env):
    _, alerts = env
    r = alerts.add_rule("vol:GC", "percentile", ">=", "90")  # coerced to float
    assert r["threshold"] == 90.0
    assert r["enabled"] is True
    assert r["label"] == "vol:GC percentile >= 90.0"
    rules = alerts.list_rules()
    assert len(rules) == 1
    assert rules[0]["id"] == r["id"]


def test_evaluate_numeric_triggers(env):
    db, alerts = env
    db.record_snapshot("vol:GC", {"vol": 0.22, "regime": "elevated", "percentile": 92})
    alerts.add_rule("vol:GC", "percentile", ">=", 90)
    out = alerts.evaluate()
    assert out["triggered_count"] == 1
    a = out["alerts"][0]
    assert a["triggered"] is True
    assert a["current"] == 92
    assert a["status"] == "ok"


def test_evaluate_categorical_and_no_trigger(env):
    db, alerts = env
    db.record_snapshot("vol:GC", {"vol": 0.10, "regime": "calm", "percentile": 20})
    alerts.add_rule("vol:GC", "regime", "==", "stressed")
    out = alerts.evaluate()
    assert out["triggered_count"] == 0
    assert out["alerts"][0]["triggered"] is False


def test_evaluate_no_data_yet(env):
    _, alerts = env
    alerts.add_rule("vol:ZZ", "regime", "==", "stressed")
    out = alerts.evaluate()
    assert out["alerts"][0]["status"] == "no data yet"
    assert out["triggered_count"] == 0


def test_disabled_rule_not_counted(env):
    db, alerts = env
    db.record_snapshot("vol:GC", {"regime": "stressed"})
    r = alerts.add_rule("vol:GC", "regime", "==", "stressed")
    assert alerts.evaluate()["triggered_count"] == 1
    assert alerts.set_enabled(r["id"], False) is True
    out = alerts.evaluate()
    assert out["triggered_count"] == 0
    assert out["alerts"][0]["triggered"] is True  # condition still holds…
    assert out["alerts"][0]["enabled"] is False  # …but it's off, so not counted


def test_remove_rule(env):
    _, alerts = env
    r = alerts.add_rule("regime:macro", "regime", "==", "risk-off")
    assert alerts.remove_rule(r["id"]) is True
    assert alerts.remove_rule(r["id"]) is False
    assert alerts.list_rules() == []


def test_evaluate_uses_latest_snapshot(env):
    db, alerts = env
    db.record_snapshot("vol:GC", {"percentile": 10}, ts="2026-01-01T00:00:00+00:00")
    db.record_snapshot("vol:GC", {"percentile": 95}, ts="2026-01-02T00:00:00+00:00")
    alerts.add_rule("vol:GC", "percentile", ">=", 90)
    a = alerts.evaluate()["alerts"][0]
    assert a["current"] == 95  # newest snapshot
    assert a["triggered"] is True
