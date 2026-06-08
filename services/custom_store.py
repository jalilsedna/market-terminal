"""Pure JSON-backed store for the custom watchlist (ROADMAP C6).

No OpenBB / numpy — just the persisted list of (asset, symbol) entries, so this
is unit-tested in CI. The live price/vol layer is `services/custom_watchlist.py`.

Persisted at `settings.custom_watchlist_path` (gitignored cache/data by default;
point at a mounted volume on Railway to survive redeploys).
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from config import get_settings

VALID_ASSETS = ("futures", "crypto", "forex", "equity", "etf")
_lock = threading.Lock()


def _path() -> Path:
    return Path(get_settings().custom_watchlist_path)


def _load() -> list[dict]:
    p = _path()
    if not p.exists():
        return []
    try:
        items = json.loads(p.read_text(encoding="utf-8"))
        return items if isinstance(items, list) else []
    except Exception:  # noqa: BLE001 — a corrupt file shouldn't crash the view
        return []


def _save(items: list[dict]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(items, indent=2), encoding="utf-8")


def list_items() -> list[dict]:
    """The stored entries (id, asset, symbol, label) — no live data."""
    with _lock:
        return _load()


def add(asset: str, symbol: str, label: str | None = None) -> dict:
    """Add an instrument; idempotent on (asset, symbol). Returns its entry."""
    asset = (asset or "").lower().strip()
    symbol = (symbol or "").strip()
    if asset not in VALID_ASSETS:
        raise ValueError(f"unknown asset {asset!r}; choose from {list(VALID_ASSETS)}")
    if not symbol:
        raise ValueError("symbol is required")
    item_id = f"{asset}:{symbol}"
    entry = {"id": item_id, "asset": asset, "symbol": symbol, "label": label or symbol}
    with _lock:
        items = _load()
        if not any(i.get("id") == item_id for i in items):
            items.append(entry)
            _save(items)
    return entry


def remove(item_id: str) -> bool:
    """Remove by id ('asset:symbol'). True if something was removed."""
    with _lock:
        items = _load()
        kept = [i for i in items if i.get("id") != item_id]
        if len(kept) == len(items):
            return False
        _save(kept)
        return True
