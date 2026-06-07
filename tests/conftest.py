"""Shared pytest fixtures.

These tests deliberately exercise only the **lightweight** layers (auth, config,
the MCP mount) so CI stays fast and network-free — no OpenBB import, no provider
calls. The "does the whole app still wire together with OpenBB" check is the
separate import-smoke job in CI (see .github/workflows/ci.yml).
"""

from __future__ import annotations

import pytest


@pytest.fixture
def auth_env(monkeypatch):
    """Configure auth credentials and rebuild the cached Settings.

    `config.get_settings` is `lru_cache`d, so any test that changes the auth
    environment must clear it before and after to avoid leaking state.
    """
    monkeypatch.setenv("AUTH_TOKEN", "tok-123")
    monkeypatch.setenv("ADMIN_USERNAME", "jalil")
    monkeypatch.setenv("ADMIN_PASSWORD", "pw-456")
    monkeypatch.setenv("SESSION_SECRET", "sekret")

    import config

    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


@pytest.fixture
def no_auth_env(monkeypatch):
    """No credentials set → auth disabled (keyless local-dev mode)."""
    for var in ("AUTH_TOKEN", "ADMIN_PASSWORD", "SESSION_SECRET"):
        monkeypatch.delenv(var, raising=False)

    import config

    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()
