"""Operational self-diagnostic (ROADMAP A6 — /doctor).

A deeper companion to /health: one call that reports provider configuration, the
EOD fallback chain, SQLite/volume state (path, writability, row counts), the
in-process cache, and a rollup of advisory **checks** (auth on, a sturdy provider
in the chain, DB persisted on a volume, optional keys). Read-only and dependency-
light (config + cache + db, no OpenBB), so it's safe to expose and unit-tested.

The router (`app/routers/doctor.py`) gates it behind the normal auth middleware
and passes the signed-in user/role through.
"""

from __future__ import annotations

from app import db
from cache import store as cache_store
from config import get_settings

_DEFAULT_DB_PATH = "cache/data/terminal.db"
_STURDY_PROVIDERS = ("fmp", "tiingo", "polygon")


def report(user: str | None = None, role: str | None = None) -> dict:
    """Assemble the diagnostic report + advisory checks."""
    s = get_settings()
    dbs = db.stats()
    chain = s.eod_provider_chain

    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    check("auth enabled", s.auth_enabled,
          "open — set AUTH_TOKEN / ADMIN_PASSWORD before exposing publicly" if not s.auth_enabled else "")
    sturdy = any(p in chain for p in _STURDY_PROVIDERS)
    check("sturdy EOD provider in chain", sturdy,
          f"chain={chain}" if sturdy else "set FMP_API_KEY and/or add tiingo/polygon to EOD_PROVIDERS")
    check("database writable", dbs.get("writable", False), dbs.get("error", ""))
    check("database on a persistent volume", dbs["path"] != _DEFAULT_DB_PATH,
          "DB_PATH is the default cache/ path — point it at a mounted volume so data survives redeploys"
          if dbs["path"] == _DEFAULT_DB_PATH else dbs["path"])
    check("movers configured", s.movers_enabled,
          "set POLYGON_API_KEY to enable the Movers tab" if not s.movers_enabled else "")
    check("fred configured", bool(s.fred_api_key),
          "set FRED_API_KEY to fill the Macro tiles + Dollar/FX panel" if not s.fred_api_key else "")

    # News-Pulse analyst (Anthropic) — live probe so a silent fallback is visible.
    from obb_layer import llm
    llm_probe = llm.probe()
    if s.llm_enabled:
        check("news-pulse analyst (Anthropic)", llm_probe.get("ok", False),
              f"model={llm_probe.get('model')}" if llm_probe.get("ok")
              else f"falling back to rule-based — {llm_probe.get('error', 'unknown error')}")

    return {
        "app": s.app_name,
        "version": "0.0.1",
        "auth": {"enabled": s.auth_enabled, "user": user, "role": role},
        "providers": {
            "configured": s.configured_providers(),
            "eod_chain": chain,
            "movers_configured": s.movers_enabled,
        },
        "database": dbs,
        "llm": llm_probe,
        "cache": cache_store.stats(),
        "precache": {"interval_min": s.precache_interval_min},
        "checks": checks,
        # Hard health = DB writable; the rest are advisory (optional keys, etc.).
        "healthy": dbs.get("writable", False),
    }
