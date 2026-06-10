"""Alpaca read-only client — tradable asset universe (OpenAlice execution venue).

Used for instrument **discovery** (search/list tradable symbols Alice can reach).
This terminal never places orders; only read-only Broker API calls (asset list)
and optional market-data lookups. Keys are the same paper/live credentials
OpenAlice uses — read-only data access only.

See docs/openalice.md for the research↔execution split.
"""

from __future__ import annotations

from typing import Any

from cache.store import cached
from config import get_settings

# Liquid ETFs we always classify as etf (Alpaca metadata alone is unreliable).
_KNOWN_ETFS = frozenset({
    "SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "TLT", "HYG", "XLF", "XLE", "XLV",
    "XLK", "XLI", "XLP", "XLY", "XLU", "XLB", "VOO", "VTI", "VEA", "VWO", "AGG",
    "BND", "LQD", "EEM", "EFA", "ARKK", "SMH", "SOXX", "IBIT", "FBTC",
})


class AlpacaDisabled(RuntimeError):
    """No Alpaca credentials configured."""


class AlpacaError(RuntimeError):
    """Alpaca request failed — message is sanitized."""


def _enabled() -> bool:
    s = get_settings()
    return bool(s.alpaca_api_key and s.alpaca_api_secret)


def _headers() -> dict[str, str]:
    s = get_settings()
    if not _enabled():
        raise AlpacaDisabled("set ALPACA_API_KEY and ALPACA_API_SECRET in .env")
    return {
        "APCA-API-KEY-ID": s.alpaca_api_key or "",
        "APCA-API-SECRET-KEY": s.alpaca_api_secret or "",
    }


def _get(path: str, params: dict | None = None) -> Any:
    import httpx

    s = get_settings()
    url = f"{s.alpaca_api_base.rstrip('/')}{path}"
    try:
        r = httpx.get(url, headers=_headers(), params=params or {}, timeout=45.0)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as exc:
        raise AlpacaError(f"Alpaca HTTP {exc.response.status_code}") from exc
    except Exception as exc:
        raise AlpacaError(f"{type(exc).__name__}: {exc}") from exc


def _terminal_asset(a: dict) -> str:
    sym = str(a.get("symbol") or "")
    name = str(a.get("name") or sym)
    klass = str(a.get("class") or "us_equity")
    if klass == "crypto":
        return "crypto"
    if sym in _KNOWN_ETFS or " ETF" in f" {name.upper()}" or name.upper().endswith(" ETF"):
        return "etf"
    if a.get("exchange") == "ARCA":
        return "etf"
    return "equity"


@cached("reference")
def _us_equity_catalog(*, status: str = "active") -> list[dict]:
    """Fetch the full US equity catalog once (cached) — filter per query in memory."""
    params: dict[str, str] = {"status": status, "asset_class": "us_equity"}
    raw = _get("/v2/assets", params)
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for a in raw:
        sym = str(a.get("symbol") or "")
        if not sym:
            continue
        name = str(a.get("name") or sym)
        out.append({
            "symbol": sym,
            "name": name,
            "asset_class": str(a.get("class") or "us_equity"),
            "terminal_asset": _terminal_asset(a),
            "tradable": bool(a.get("tradable")),
            "exchange": a.get("exchange"),
        })
    return out


def list_assets(
    *,
    status: str = "active",
    asset_class: str | None = None,
    search: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List tradable US equities/ETFs from Alpaca's asset catalog.

  `search`: case-insensitive substring filter on symbol or name.
    """
    if asset_class and asset_class != "us_equity":
        return []
    catalog = _us_equity_catalog(status=status)
    q = (search or "").strip().upper()
    out: list[dict] = []
    for row in catalog:
        sym = row["symbol"]
        name = row["name"]
        if q and q not in sym.upper() and q not in name.upper():
            continue
        out.append(row)
        if len(out) >= limit:
            break
    return out
