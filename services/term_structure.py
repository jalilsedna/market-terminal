"""V5 — Futures Term Structure domain logic (SPEC.md §4 V5).

Reads the forward curve and classifies it: contango (back > front → carry cost,
storage) vs backwardation (back < front → tight supply / convenience yield),
with the front/back spread and slope. The real edge is GC and energy roll
context.

Services never import OpenBB directly — they call `obb_layer/`.
"""

from __future__ import annotations

from typing import Any

from obb_layer import term_structure as ts

# Curve roots to track (SPEC §4 V5: GC + energy). yfinance continuation symbols.
CURVE_INSTRUMENTS: dict[str, str] = {
    "GC": "Gold (GC=F)",
    "CL": "WTI Crude (CL=F)",
    "NG": "Natural Gas (NG=F)",
}
_SYMBOLS = {"GC": "GC=F", "CL": "CL=F", "NG": "NG=F"}


def _num(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _classify(symbol: str) -> dict:
    points_raw = ts.futures_curve(symbol)
    points = [
        {"expiration": str(p.get("expiration"))[:10], "price": _num(p.get("price"))}
        for p in points_raw
        if _num(p.get("price")) is not None
    ]
    points.sort(key=lambda p: p["expiration"])
    if len(points) < 2:
        raise ValueError("curve has fewer than 2 expirations")

    front, back = points[0]["price"], points[-1]["price"]
    spread = round(back - front, 4)
    spread_pct = round((back - front) / front * 100, 2) if front else None
    structure = "contango" if back > front else "backwardation" if back < front else "flat"
    return {
        "structure": structure,
        "front_expiration": points[0]["expiration"],
        "front_price": front,
        "back_expiration": points[-1]["expiration"],
        "back_price": back,
        "front_back_spread": spread,
        "front_back_spread_pct": spread_pct,
        "num_expirations": len(points),
        "curve": points,
    }


def curve(code: str) -> dict:
    """Term-structure classification for one curve root (e.g. 'GC')."""
    key = code.upper()
    if key not in _SYMBOLS:
        raise ValueError(f"unknown curve '{code}'; known: {', '.join(_SYMBOLS)}")
    return {"code": key, "name": CURVE_INSTRUMENTS[key], **_classify(_SYMBOLS[key])}


def dashboard() -> dict:
    """Term structure across all tracked curves; each fault-tolerant."""
    out: dict[str, dict] = {}
    for key, name in CURVE_INSTRUMENTS.items():
        try:
            out[key] = {"ok": True, **curve(key)}
        except Exception as exc:  # noqa: BLE001 — one curve must not sink the view
            out[key] = {"ok": False, "code": key, "name": name,
                        "error": f"{type(exc).__name__}: {exc}"[:200]}
    return out
