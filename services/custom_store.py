"""Custom-watchlist store (ROADMAP C6) — now SQLite-backed (ROADMAP C2).

The public surface (add / remove / list_items) is unchanged; storage moved from
a JSON file to the SQLite layer in `app/db.py`, so the watchlist survives
restarts and (on a Railway volume) redeploys. No OpenBB — unit-tested in CI.
"""

from __future__ import annotations

from app import db

VALID_ASSETS = ("futures", "crypto", "forex", "equity", "etf")


def list_items() -> list[dict]:
    """The stored entries (id, asset, symbol, label) — no live data."""
    return db.watchlist_list()


def add(asset: str, symbol: str, label: str | None = None) -> dict:
    """Add an instrument; idempotent on (asset, symbol). Returns its entry."""
    asset = (asset or "").lower().strip()
    symbol = (symbol or "").strip()
    if asset not in VALID_ASSETS:
        raise ValueError(f"unknown asset {asset!r}; choose from {list(VALID_ASSETS)}")
    if not symbol:
        raise ValueError("symbol is required")
    item_id = f"{asset}:{symbol}"
    db.watchlist_add(item_id, asset, symbol, label or symbol)
    return {"id": item_id, "asset": asset, "symbol": symbol, "label": label or symbol}


def remove(item_id: str) -> bool:
    """Remove by id ('asset:symbol'). True if something was removed."""
    return db.watchlist_remove(item_id)
