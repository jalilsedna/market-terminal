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
        r = httpx.get(url, headers=_headers(), params=params or {}, timeout=30.0)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as exc:
        raise AlpacaError(f"Alpaca HTTP {exc.response.status_code}") from exc
    except Exception as exc:
        raise AlpacaError(f"{type(exc).__name__}: {exc}") from exc


@cached("reference")
def list_assets(
    *,
    status: str = "active",
    asset_class: str | None = None,
    search: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List tradable US equities/ETFs from Alpaca's asset catalog.

    `asset_class`: us_equity | crypto (when supported by the account).
    `search`: case-insensitive substring filter on symbol or name.
    """
    params: dict[str, str] = {"status": status}
    if asset_class:
        params["asset_class"] = asset_class
    raw = _get("/v2/assets", params)
    if not isinstance(raw, list):
        return []
    out = []
    q = (search or "").strip().upper()
    for a in raw:
        sym = str(a.get("symbol") or "")
        name = str(a.get("name") or sym)
        if q and q not in sym.upper() and q not in name.upper():
            continue
        klass = str(a.get("class") or "us_equity")
        terminal_asset = "crypto" if klass == "crypto" else "etf" if a.get("exchange") == "ARCA" and sym.endswith(("X", "Y")) else "equity"
        if klass == "us_equity" and sym in ("SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "TLT", "HYG", "XLF", "XLE"):
            terminal_asset = "etf"
        out.append({
            "symbol": sym,
            "name": name,
            "asset_class": klass,
            "terminal_asset": terminal_asset,
            "tradable": bool(a.get("tradable")),
            "exchange": a.get("exchange"),
        })
        if len(out) >= limit:
            break
    return out
