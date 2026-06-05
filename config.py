"""Central configuration.

Loads all settings and provider API keys from a local `.env` file (gitignored,
never committed). This is the single source of truth for secrets — we do not
depend on OpenBB Hub (it is being retired). See SPEC.md §6.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application + provider settings, populated from environment / `.env`.

    All fields are optional so the app can boot on 100% free providers
    (yfinance, fred, cftc, ...) with no keys configured. Add keys to `.env`
    only when you need the corresponding paid provider.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_name: str = "Multi-Asset Research Terminal"
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    # --- Pre-cache scheduler (Phase 3) ---
    # Minutes between background cache-warming cycles; 0 disables the scheduler.
    precache_interval_min: int = 30

    # --- Provider API keys (optional; free providers need none) ---
    fmp_api_key: str | None = None
    fred_api_key: str | None = None
    benzinga_api_key: str | None = None
    intrinio_api_key: str | None = None
    tiingo_api_key: str | None = None
    eia_api_key: str | None = None

    def configured_providers(self) -> dict[str, bool]:
        """Map of provider -> whether a key is present. Useful for diagnostics."""
        return {
            "fmp": bool(self.fmp_api_key),
            "fred": bool(self.fred_api_key),
            "benzinga": bool(self.benzinga_api_key),
            "intrinio": bool(self.intrinio_api_key),
            "tiingo": bool(self.tiingo_api_key),
            "eia": bool(self.eia_api_key),
        }


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
