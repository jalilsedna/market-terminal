"""V5 — Futures Term Structure domain logic (SPEC.md §4 V5).

Reads forward curves and classifies them: contango (back > front → carry cost,
storage) vs backwardation (back < front → tight supply / convenience yield),
with the front/back spread and slope. Covers GC + energy (roll context) and the
VIX curve as a fear gauge — where VIX *backwardation* signals stress and
contango signals calm.

Services never import OpenBB directly — they call `obb_layer/`.
"""

from __future__ import annotations

from typing import Any

from obb_layer import term_structure as ts

# code -> (display name, curve symbol, provider). GC + energy via yfinance; the
# VIX fear gauge via cboe (SPEC §4 V5).
CURVE_SPECS: dict[str, tuple[str, str, str]] = {
    "GC": ("Gold (GC=F)", "GC=F", "yfinance"),
    "CL": ("WTI Crude (CL=F)", "CL=F", "yfinance"),
    "NG": ("Natural Gas (NG=F)", "NG=F", "yfinance"),
    "VIX": ("VIX (fear gauge)", "VIX", "cboe"),
}


def _num(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _classify(symbol: str, provider: str, *, is_vix: bool = False) -> dict:
    points_raw = ts.futures_curve(symbol, provider=provider)
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

    result = {
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
    if is_vix:
        # VIX is inverted vs commodities: backwardation = front fear bid = stress.
        result["fear_signal"] = "stress / risk-off" if structure == "backwardation" else (
            "calm / risk-on" if structure == "contango" else "neutral")
    return result


def curve(code: str) -> dict:
    """Term-structure classification for one curve root (e.g. 'GC', 'VIX')."""
    key = code.upper()
    if key not in CURVE_SPECS:
        raise ValueError(f"unknown curve '{code}'; known: {', '.join(CURVE_SPECS)}")
    name, symbol, provider = CURVE_SPECS[key]
    return {"code": key, "name": name, "provider": provider,
            **_classify(symbol, provider, is_vix=(key == "VIX"))}


def dashboard() -> dict:
    """Term structure across all tracked curves (GC + energy + VIX); fault-tolerant."""
    out: dict[str, dict] = {}
    for key, (name, _symbol, _provider) in CURVE_SPECS.items():
        try:
            out[key] = {"ok": True, **curve(key)}
        except Exception as exc:  # noqa: BLE001 — one curve must not sink the view
            out[key] = {"ok": False, "code": key, "name": name,
                        "error": f"{type(exc).__name__}: {exc}"[:200]}
    return out
