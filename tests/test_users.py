"""User store + password hashing (ROADMAP F2) — no OpenBB, runs in CI."""

from __future__ import annotations

import pytest


@pytest.fixture
def users(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("ADMIN_USERNAME", "boss")
    monkeypatch.setenv("ADMIN_PASSWORD", "envsecret1")
    import config

    config.get_settings.cache_clear()
    from app.auth import users as u

    yield u
    config.get_settings.cache_clear()


def test_hash_roundtrip():
    from app.auth import hash_password, verify_hash

    h = hash_password("hunter2!")
    assert verify_hash("hunter2!", h)
    assert not verify_hash("wrong", h)
    assert not verify_hash("x", "garbage")  # malformed hash → no match


def test_env_admin_bootstrap(users):
    assert users.verify_password("boss", "envsecret1")
    assert not users.verify_password("boss", "nope")
    assert users.role("boss") == "admin"
    assert users.role("ghost") is None
    assert users.exists("boss")


def test_create_and_verify_db_user(users):
    assert users.create("alice", "password123") is True
    assert users.create("alice", "password123") is False  # taken
    assert users.verify_password("alice", "password123")
    assert not users.verify_password("alice", "wrong")
    assert users.role("alice") == "user"
    assert [u["username"] for u in users.list()] == ["alice"]


def test_disable_blocks_login(users):
    users.create("bob", "password123")
    assert users.set_disabled("bob", True) is True
    assert not users.verify_password("bob", "password123")
    assert users.role("bob") is None
    users.set_disabled("bob", False)
    assert users.verify_password("bob", "password123")


def test_create_admin_role(users):
    users.create("admin2", "password123", role="admin")
    assert users.role("admin2") == "admin"
