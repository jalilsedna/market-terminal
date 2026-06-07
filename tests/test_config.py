"""Settings behaviour — the auth gate's on/off logic and provider map."""

from __future__ import annotations


def test_auth_enabled_when_token_set(auth_env):
    from config import get_settings

    assert get_settings().auth_enabled is True


def test_auth_disabled_without_credentials(no_auth_env):
    from config import get_settings

    s = get_settings()
    assert s.auth_enabled is False
    # Keyless dev still boots on free providers — no keys required.
    assert s.admin_password is None
    assert s.auth_token is None


def test_auth_enabled_with_only_admin_password(monkeypatch):
    """A browser-only deploy (admin password, no Bearer token) still enables the
    gate."""
    monkeypatch.delenv("AUTH_TOKEN", raising=False)
    monkeypatch.setenv("ADMIN_PASSWORD", "pw")
    import config

    config.get_settings.cache_clear()
    try:
        assert config.get_settings().auth_enabled is True
    finally:
        config.get_settings.cache_clear()


def test_configured_providers_shape(no_auth_env):
    from config import get_settings

    providers = get_settings().configured_providers()
    assert set(providers) == {"fmp", "fred", "benzinga", "intrinio", "tiingo", "eia"}
    assert all(v is False for v in providers.values())
