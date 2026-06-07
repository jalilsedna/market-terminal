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

    # --- Auth (Phase A8 — required before the service is public) ---
    # The terminal is single-user research, but once it's reachable on the
    # internet (Railway) the web UI, REST API, and mounted MCP feed must be
    # gated, or anyone can hit it and burn the provider keys. Two credentials:
    #   * auth_token   — Bearer token for programmatic clients (Alice / MCP / API)
    #   * admin_*      — username/password for the browser /login page
    # Both are OPTIONAL: with neither set, auth is DISABLED so local dev is
    # unchanged. `auth_enabled` is true as soon as either is configured, which is
    # mandatory on any public deploy (see docs/deploy-railway.md).
    auth_token: str | None = None
    admin_username: str = "admin"
    admin_password: str | None = None
    # Signs the browser session cookie. Keep it stable across restarts so logins
    # survive redeploys; falls back to auth_token if unset. Generate with
    # `openssl rand -hex 32`.
    session_secret: str | None = None
    # Public URL of the deployed terminal (for docs / Alice's .mcp.json), e.g.
    # https://market-terminal.up.railway.app — informational only.
    public_base_url: str | None = None

    # --- Pre-cache scheduler (Phase 3) ---
    # Minutes between background cache-warming cycles; 0 disables the scheduler.
    precache_interval_min: int = 30

    # --- MCP server (Phase 3; see mcp_server.py) ---
    # Host/port used only when the MCP server runs over HTTP (streamable-http),
    # e.g. so a separate app like OpenAlice can pull research over a URL. Port
    # defaults to 8001 to avoid clashing with the REST API on 8000.
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8001

    # --- Execution app (OpenAlice) ---
    # URL of the SEPARATE execution app, framed in the terminal's Execution tab.
    # Default is OpenAlice's dev UI. Execution lives there, never in this repo.
    alice_url: str = "http://localhost:5173"

    # --- Provider API keys (optional; free providers need none) ---
    fmp_api_key: str | None = None
    fred_api_key: str | None = None
    benzinga_api_key: str | None = None
    intrinio_api_key: str | None = None
    tiingo_api_key: str | None = None
    eia_api_key: str | None = None

    @property
    def auth_enabled(self) -> bool:
        """Whether access control is active. True as soon as a Bearer token or an
        admin password is configured; false (open) for keyless local dev."""
        return bool(self.auth_token or self.admin_password)

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
