"""OpenBB client bootstrap.

Single import site for OpenBB. Loads provider credentials from our config
(`.env`) into OpenBB's in-process credential store at startup, so we never rely
on OpenBB Hub (being retired) and never scatter keys through the code.
"""

from __future__ import annotations

from config import get_settings


def get_obb():
    """Return the configured OpenBB application object (`obb`).

    Imported lazily so the rest of the app (and tests) can load without pulling
    in the full OpenBB Platform.
    """
    from openbb import obb  # noqa: PLC0415  (intentional lazy import)

    settings = get_settings()
    creds = obb.user.credentials

    # Push any keys present in .env into OpenBB's credential store.
    _maybe_set(creds, "fmp_api_key", settings.fmp_api_key)
    _maybe_set(creds, "fred_api_key", settings.fred_api_key)
    _maybe_set(creds, "benzinga_api_key", settings.benzinga_api_key)
    _maybe_set(creds, "intrinio_api_key", settings.intrinio_api_key)
    _maybe_set(creds, "tiingo_token", settings.tiingo_api_key)
    # Massive.com == Polygon.io (rebranded); the key authenticates OpenBB's
    # `polygon` provider via the still-supported api.polygon.io endpoint.
    _maybe_set(creds, "polygon_api_key", settings.polygon_api_key)
    _maybe_set(creds, "eia_api_key", settings.eia_api_key)

    return obb


def _maybe_set(creds, attr: str, value: str | None) -> None:
    """Set a credential attribute only if we actually have a value for it."""
    if value:
        try:
            setattr(creds, attr, value)
        except (AttributeError, ValueError):
            # OpenBB renames credential fields across versions; don't hard-fail
            # boot just because one field moved. The probe script surfaces this.
            pass
