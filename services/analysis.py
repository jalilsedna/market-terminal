"""Analysis layer — interpreted signals from the raw views (ROADMAP C3).

Pattern adapted from anthropics/financial-services (Apache-2.0): a focused,
methodical analysis that yields a structured work product for human review,
explicitly labeled **research context — not investment advice or a trade
trigger**. The analytics here are built for *this* terminal's domain (futures /
macro positioning), since that repo's skills target equity/IB workflows.

Composes the existing services (cot, macro, term_structure, screener) — it does
no new provider calls, only interprets their cached output. Each analysis is
fault-tolerant: missing inputs degrade the read rather than failing it.

Services never import OpenBB directly; they call `obb_layer/` (here, indirectly
through the other services).
"""

from __future__ import annotations

from typing import Any

from services import cot as cot_svc
from services import macro as macro_svc
from services import screener as screener_svc
from services import term_structure as ts_svc

DISCLAIMER = "Research context only — interpreted positioning/regime signals, not investment advice or a trade trigger."

# Crowding thresholds on the 1-year net-positioning percentile.
_CROWDED_HI = 85.0
_CROWDED_LO = 15.0

# S&P sectors split by risk character (used for the regime breadth read).
_DEFENSIVE = {"Utilities", "Consumer Staples", "Health Care", "Real Estate"}
_CYCLICAL = {
    "Technology", "Consumer Discretionary", "Financials", "Industrials",
    "Materials", "Energy", "Communication Services",
}


def _num(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


# --- COT positioning signals -------------------------------------------------

def _cot_signal(entry: dict) -> dict:
    """Interpret one contract's COT entry into a positioning read."""
    nc = entry.get("non_commercial", {}) or {}
    comm = entry.get("commercial", {}) or {}
    net = _num(nc.get("net"))
    chg = _num(nc.get("net_change_1w"))
    pct_1y = _num((nc.get("range_1y") or {}).get("percentile_in_range"))
    pct_3y = _num((nc.get("range_3y") or {}).get("percentile_in_range"))

    if pct_1y is None:
        positioning = "n/a"
    elif pct_1y >= _CROWDED_HI:
        positioning = "crowded long"
    elif pct_1y <= _CROWDED_LO:
        positioning = "crowded short"
    else:
        positioning = "mid-range"

    if chg is None:
        weekly_shift = "n/a"
    elif chg > 0:
        weekly_shift = "large specs adding net longs"
    elif chg < 0:
        weekly_shift = "large specs cutting net longs"
    else:
        weekly_shift = "flat w/w"

    if positioning == "crowded long":
        bias = "stretched long — contrarian downside risk if it unwinds"
    elif positioning == "crowded short":
        bias = "stretched short — squeeze / upside risk if it covers"
    else:
        bias = "no positioning extreme"

    return {
        "non_commercial_net": net,
        "net_change_1w": chg,
        "percentile_1y": pct_1y,
        "percentile_3y": pct_3y,
        "commercial_net": _num(comm.get("net")),
        "positioning": positioning,
        "weekly_shift": weekly_shift,
        "bias": bias,
        "report_date": entry.get("report_date"),
    }


def cot_signals() -> dict:
    """Positioning read across the watchlist (contrarian-at-extremes lens)."""
    dash = cot_svc.dashboard()
    signals: dict[str, dict] = {}
    extremes: list[str] = []
    for code, entry in dash.items():
        if not entry.get("ok"):
            signals[code] = {"ok": False, "name": entry.get("name"), "error": entry.get("error")}
            continue
        sig = {"ok": True, "name": entry.get("name"), **_cot_signal(entry)}
        signals[code] = sig
        if sig["positioning"] in ("crowded long", "crowded short"):
            extremes.append(f"{code} {sig['positioning']}")
    return {
        "method": "Non-commercial (large-spec) net positioning vs its 1y/3y range; "
                  "≥85th pct = crowded long, ≤15th = crowded short. Extremes read "
                  "as contrarian risk, not a signal.",
        "extremes": extremes or None,
        "signals": signals,
        "disclaimer": DISCLAIMER,
    }


# --- Macro regime read -------------------------------------------------------

def _vote(leans: str) -> int:
    return {"risk-on": 1, "risk-off": -1}.get(leans, 0)


def regime() -> dict:
    """Risk-on / risk-off read from VIX structure, sector breadth, dollar, index."""
    signals: list[dict] = []

    # VIX term structure (fear gauge): backwardation = stress.
    try:
        vix = ts_svc.curve("VIX")
        if vix.get("structure"):
            leans = "risk-off" if vix["structure"] == "backwardation" else "risk-on"
            signals.append({"name": "VIX curve", "reading": vix["structure"],
                            "detail": vix.get("fear_signal"), "leans": leans})
    except Exception:  # noqa: BLE001
        pass

    # Sector rotation breadth: defensive leadership = risk-off.
    try:
        rot = screener_svc.sector_rotation()
        leaders = rot.get("leaders") or []
        d = sum(1 for s in leaders if s in _DEFENSIVE)
        c = sum(1 for s in leaders if s in _CYCLICAL)
        if d or c:
            leans = "risk-off" if d > c else "risk-on" if c > d else "mixed"
            signals.append({"name": "Sector leadership", "reading": ", ".join(leaders[:3]),
                            "detail": f"{d} defensive / {c} cyclical in top-3", "leans": leans})
    except Exception:  # noqa: BLE001
        pass

    # Dollar + index trend from the macro dashboard.
    try:
        m = macro_svc.build_dashboard()
        fx = m.get("dollar_fx", {})
        if fx.get("ok"):
            usd_1w = _num((fx.get("dollar_index") or {}).get("change_1w_pct"))
            if usd_1w is not None:
                leans = "risk-off" if usd_1w > 0 else "risk-on" if usd_1w < 0 else "mixed"
                signals.append({"name": "Broad USD (1w)", "reading": f"{usd_1w:+.2f}%",
                                "detail": "stronger USD = risk-off", "leans": leans})
        idx = m.get("indices", {})
        if idx.get("ok"):
            spx = (idx.get("indices") or {}).get("^GSPC", {})
            spx_1w = _num(spx.get("change_1w_pct"))
            if spx_1w is not None:
                leans = "risk-on" if spx_1w > 0 else "risk-off" if spx_1w < 0 else "mixed"
                signals.append({"name": "S&P 500 (1w)", "reading": f"{spx_1w:+.2f}%",
                                "detail": None, "leans": leans})
    except Exception:  # noqa: BLE001
        pass

    score = sum(_vote(s["leans"]) for s in signals)
    if not signals:
        label = "unknown (no inputs available)"
    elif score >= 2:
        label = "risk-on"
    elif score <= -2:
        label = "risk-off"
    else:
        label = "mixed / neutral"

    return {
        "regime": label,
        "score": score,
        "method": "Each input votes risk-on (+1) / risk-off (-1); sum ≥+2 risk-on, ≤-2 risk-off, else mixed.",
        "signals": signals,
        "disclaimer": DISCLAIMER,
    }
