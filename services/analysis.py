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

from obb_layer.symbols import WATCHLIST
from services import cot as cot_svc
from services import macro as macro_svc
from services import news as news_svc
from services import screener as screener_svc
from services import term_structure as ts_svc
from services import watchlist as watchlist_svc

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


# --- Per-instrument brief ----------------------------------------------------

def brief(instrument: str) -> dict:
    """"What's moving this contract" — synthesis of regime, positioning, price,
    term structure (where it exists), and tagged news for one watchlist symbol.

    Each component is independent and fault-tolerant; a missing one is omitted
    rather than failing the brief. Rule-based synthesis — no recommendations.
    """
    key = (instrument or "").upper()
    if key not in WATCHLIST:
        raise ValueError(f"unknown instrument '{instrument}'; known: {', '.join(WATCHLIST)}")
    inst = WATCHLIST[key]
    out: dict[str, Any] = {"code": key, "name": inst.name, "disclaimer": DISCLAIMER}

    # Overall macro context.
    reg = {}
    try:
        r = regime()
        reg = {"regime": r.get("regime"), "score": r.get("score")}
    except Exception:  # noqa: BLE001
        pass
    out["regime"] = reg or None

    # Price / momentum.
    price = {}
    try:
        w = watchlist_svc.instrument_summary(key)
        f = w.get("future", {})
        price = {
            "close": f.get("close"),
            "change_1d_pct": f.get("change_1d_pct"),
            "change_1w_pct": f.get("change_1w_pct"),
            "change_1m_pct": f.get("change_1m_pct"),
            "atr_14_pct": w.get("atr_14_pct"),
        }
    except Exception:  # noqa: BLE001
        pass
    out["price"] = price or None

    # COT positioning read for this contract.
    cot = {}
    try:
        cot = _cot_signal(cot_svc.positioning(instrument=key))
    except Exception:  # noqa: BLE001
        pass
    out["cot"] = cot or None

    # Term structure (only contracts we carry a curve for, e.g. GC).
    if key in getattr(ts_svc, "CURVE_SPECS", {}):
        try:
            t = ts_svc.curve(key)
            out["term_structure"] = {
                "structure": t.get("structure"),
                "front_back_spread_pct": t.get("front_back_spread_pct"),
            }
        except Exception:  # noqa: BLE001
            out["term_structure"] = None

    # Tagged news for this instrument (top few).
    try:
        feed = news_svc.feed(instrument=key, limit=5)
        out["news"] = [
            {"date": h.get("date"), "title": h.get("title"), "source": h.get("source"), "url": h.get("url")}
            for h in (feed.get("headlines") or [])[:5]
        ]
    except Exception:  # noqa: BLE001
        out["news"] = None

    # One-line factual read assembled from the parts (no advice).
    bits: list[str] = []
    if cot.get("positioning") and cot["positioning"] != "n/a":
        pctl = cot.get("percentile_1y")
        bits.append(f"{cot['positioning']}" + (f" ({pctl:.0f}th pct 1y)" if pctl is not None else ""))
    if cot.get("weekly_shift") and cot["weekly_shift"] not in ("n/a", "flat w/w"):
        bits.append(cot["weekly_shift"])
    if reg.get("regime"):
        bits.append(f"macro regime {reg['regime']}")
    if price.get("change_1w_pct") is not None:
        bits.append(f"price {price['change_1w_pct']:+.2f}% 1w")
    if out.get("term_structure", {}) and out["term_structure"] and out["term_structure"].get("structure"):
        bits.append(f"curve {out['term_structure']['structure']}")
    out["read"] = f"{inst.name}: " + "; ".join(bits) + "." if bits else f"{inst.name}: insufficient data."

    return out


# --- Term-structure signal (flip / steepening) -------------------------------

def _ts_compare(now: dict, prior: dict) -> tuple[str | None, str | None]:
    """Return (flip, trend) between two curve readings of the same root."""
    ns, ps = now.get("structure"), prior.get("structure")
    flip = f"{ps} → {ns}" if (ns and ps and ns != ps) else None
    nsp, psp = _num(now.get("front_back_spread_pct")), _num(prior.get("front_back_spread_pct"))
    trend = None
    if nsp is not None and psp is not None and ns == ps:
        if ns == "contango":
            trend = "contango steepening" if nsp > psp else "contango flattening" if nsp < psp else "stable"
        elif ns == "backwardation":
            trend = "backwardation deepening" if nsp < psp else "backwardation easing" if nsp > psp else "stable"
    return flip, trend


def _ts_interpret(code: str, now: dict, flip: str | None, trend: str | None) -> str:
    """Plain-language read of a curve's move (VIX inverted vs commodities)."""
    s = now.get("structure")
    if code == "VIX":
        if flip and flip.endswith("backwardation"):
            return "VIX flipped into backwardation — stress spike / risk-off building"
        if flip and flip.endswith("contango"):
            return "VIX flipped back to contango — stress resolving"
        return {
            "contango steepening": "VIX contango steepening — complacency",
            "contango flattening": "VIX contango flattening — stress building at the front",
            "backwardation deepening": "VIX backwardation deepening — stress intensifying",
            "backwardation easing": "VIX backwardation easing — stress receding",
        }.get(trend or "", f"VIX {s} — stable")
    # Commodities: backwardation = tight supply / convenience yield; contango = carry.
    if flip and flip.endswith("backwardation"):
        return f"{code} flipped into backwardation — tightening / supportive"
    if flip and flip.endswith("contango"):
        return f"{code} flipped into contango — easing / carry"
    return {
        "backwardation deepening": f"{code} backwardation deepening — tightening",
        "backwardation easing": f"{code} backwardation easing",
        "contango steepening": f"{code} contango steepening — looser",
        "contango flattening": f"{code} contango flattening",
    }.get(trend or "", f"{code} {s} — stable")


def term_structure_signal(lookback_days: int = 7) -> dict:
    """Detect contango↔backwardation flips and steepening across the tracked
    curves (now vs ~`lookback_days` ago). VIX is the reliable read; the yfinance
    commodity curves degrade where unavailable.
    """
    from datetime import date as _date, timedelta

    prior_date = (_date.today() - timedelta(days=lookback_days)).isoformat()
    signals: dict[str, dict] = {}
    for code in getattr(ts_svc, "CURVE_SPECS", {}):
        try:
            now = ts_svc.curve(code)
            prior = ts_svc.curve(code, date=prior_date)
            flip, trend = _ts_compare(now, prior)
            signals[code] = {
                "ok": True,
                "structure_now": now.get("structure"),
                "spread_pct_now": now.get("front_back_spread_pct"),
                "structure_prior": prior.get("structure"),
                "spread_pct_prior": prior.get("front_back_spread_pct"),
                "prior_date": prior_date,
                "flip": flip,
                "trend": trend,
                "read": _ts_interpret(code, now, flip, trend),
            }
        except Exception as exc:  # noqa: BLE001 — degrade unavailable curves
            signals[code] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:160]}
    return {
        "method": f"Curve structure now vs ~{lookback_days}d ago. Flip = contango↔backwardation "
                  "change; steepening/deepening from the front-back spread. VIX inverted: "
                  "backwardation = stress.",
        "signals": signals,
        "disclaimer": DISCLAIMER,
    }
