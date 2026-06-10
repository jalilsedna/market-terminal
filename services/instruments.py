"""Unified instrument registry — the terminal's tracked universe.

All forex, futures, crypto, equity, and ETF symbols the user adds live here
(SQLite). Views iterate this list instead of a hardcoded futures map. Optional
metadata (COT code, TradingView symbol, news proxy) enriches capability-aware
panels. Starts empty — no bootstrap seeds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from obb_layer.symbols import INSTRUMENT_TEMPLATES, template_for
from services import custom_store

ASSET_CLASSES = custom_store.VALID_ASSETS

# Reference futures seeded on first boot so the terminal isn't blank out of the
# box (COT / term-structure / vol have something to read). Users can remove any
# of them; the seed only runs when the registry is completely empty, so a
# deliberate "remove all" survives a restart only until the registry empties.
DEFAULT_SEED = ("6E", "6B", "GC", "NQ", "YM")

# Per-asset capabilities (panels degrade when data unavailable).
_BASE_CAPS: dict[str, set[str]] = {
    "futures": {"price", "vol", "news", "cot", "term_structure"},
    "crypto": {"price", "vol", "news"},
    "forex": {"price", "vol", "news"},
    "equity": {"price", "vol", "news", "fundamentals"},
    "etf": {"price", "vol", "news", "fundamentals"},
}


@dataclass
class TrackedInstrument:
    id: str
    asset: str
    symbol: str
    label: str
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def code(self) -> str | None:
        return self.meta.get("code") or (self.symbol.replace("=F", "") if self.asset == "futures" else None)

    def capabilities(self) -> dict[str, bool]:
        caps = set(_BASE_CAPS.get(self.asset, {"price", "vol"}))
        out = {c: c in caps for c in ("price", "vol", "news", "cot", "term_structure", "fundamentals")}
        if "cot" in caps and not self.meta.get("cot_code"):
            out["cot"] = False
        if "term_structure" in caps:
            from services import term_structure as ts_svc

            root = self.code or self.symbol.replace("=F", "")
            out["term_structure"] = root in getattr(ts_svc, "CURVE_SPECS", {})
        if "news" in caps:
            out["news"] = bool(self.meta.get("news_symbol") or self.asset in ("equity", "etf", "crypto"))
        return out

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "asset": self.asset,
            "symbol": self.symbol,
            "label": self.label,
            "meta": self.meta,
            "capabilities": self.capabilities(),
        }


def _from_row(row: dict) -> TrackedInstrument:
    return TrackedInstrument(
        id=row["id"],
        asset=row["asset"],
        symbol=row["symbol"],
        label=row.get("label") or row["symbol"],
        meta=row.get("meta") or {},
    )


def list_all() -> list[TrackedInstrument]:
    return [_from_row(r) for r in custom_store.list_items()]


def get(item_id: str) -> TrackedInstrument | None:
    for inst in list_all():
        if inst.id == item_id:
            return inst
    return None


def resolve(ref: str) -> TrackedInstrument:
    """Resolve by id ('crypto:BTC-USD'), legacy code ('GC'), or symbol."""
    key = (ref or "").strip()
    if not key:
        raise ValueError("instrument reference is required")
    hit = get(key)
    if hit:
        return hit
    upper = key.upper()
    for inst in list_all():
        if inst.id.upper() == upper:
            return inst
        if (inst.code or "").upper() == upper:
            return inst
        if inst.symbol.upper() == upper:
            return inst
        if inst.label.upper() == upper:
            return inst
    raise ValueError(f"unknown instrument {ref!r}; add it to the registry first")


def add(asset: str, symbol: str, label: str | None = None, meta: dict | None = None) -> TrackedInstrument:
    asset = (asset or "").lower().strip()
    symbol = (symbol or "").strip()
    merged_meta = {**template_for(asset, symbol), **(meta or {})}
    default_label = merged_meta.get("name") or symbol
    row = custom_store.add(asset, symbol, label or default_label, merged_meta)
    return _from_row(row)


def remove(item_id: str) -> bool:
    return custom_store.remove(item_id)


def seed_defaults() -> int:
    """Seed the reference futures iff the registry is empty. Returns count added.

    Idempotent and safe to call on every startup: it no-ops the moment there is
    at least one tracked instrument, so user-added/removed state is preserved.
    """
    if custom_store.list_items():
        return 0
    added = 0
    for code in DEFAULT_SEED:
        tmpl = INSTRUMENT_TEMPLATES.get(code)
        if not tmpl:
            continue
        add("futures", tmpl.yf_symbol, tmpl.name)
        added += 1
    return added


def news_wire_targets() -> dict[str, TrackedInstrument]:
    """Instruments that can supply per-symbol news (proxy or direct)."""
    out: dict[str, TrackedInstrument] = {}
    for inst in list_all():
        if not inst.capabilities().get("news"):
            continue
        key = inst.code or inst.id
        out[key] = inst
    return out
