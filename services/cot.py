"""COT / Positioning — weekly CFTC data for tracked futures with a cot_code.

Only instruments in the registry that carry `meta.cot_code` appear in the
dashboard. Use `cot_search` to discover codes when adding new contracts.
"""

from __future__ import annotations

from typing import Any

from obb_layer import cot
from services import instruments as reg

NC_LONG = "non_commercial_positions_long_all"
NC_SHORT = "non_commercial_positions_short_all"
C_LONG = "commercial_positions_long_all"
C_SHORT = "commercial_positions_short_all"
NR_LONG = "non_reportable_positions_long_all"
NR_SHORT = "non_reportable_positions_short_all"
OPEN_INTEREST = "open_interest_all"

WEEKS_1Y = 52
WEEKS_3Y = 156


def _num(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _net(row: dict, long_key: str, short_key: str) -> float | None:
    long_, short_ = _num(row.get(long_key)), _num(row.get(short_key))
    if long_ is None or short_ is None:
        return None
    return long_ - short_


def _range_stats(series: list[float], current: float) -> dict | None:
    if not series:
        return None
    lo, hi = min(series), max(series)
    pct = round((current - lo) / (hi - lo) * 100, 1) if hi != lo else None
    return {"min": round(lo), "max": round(hi), "percentile_in_range": pct, "weeks": len(series)}


def summarize(records: list[dict], trend_weeks: int = 12) -> dict:
    rows = [r for r in records if r.get("date")]
    if not rows:
        raise ValueError("no COT rows returned")

    latest = rows[-1]
    nc_net_series = [n for r in rows if (n := _net(r, NC_LONG, NC_SHORT)) is not None]
    c_net_series = [n for r in rows if (n := _net(r, C_LONG, C_SHORT)) is not None]

    nc_net = _net(latest, NC_LONG, NC_SHORT)
    c_net = _net(latest, C_LONG, C_SHORT)
    nr_net = _net(latest, NR_LONG, NR_SHORT)
    prev_nc_net = nc_net_series[-2] if len(nc_net_series) >= 2 else None
    prev_c_net = c_net_series[-2] if len(c_net_series) >= 2 else None

    trend = [
        {"date": str(r.get("date"))[:10], "non_commercial_net": _net(r, NC_LONG, NC_SHORT),
         "commercial_net": _net(r, C_LONG, C_SHORT)}
        for r in rows[-trend_weeks:]
    ]

    return {
        "contract": latest.get("market_and_exchange_names"),
        "report_date": str(latest.get("date"))[:10],
        "open_interest": _num(latest.get(OPEN_INTEREST)),
        "history_weeks": len(rows),
        "non_commercial": {
            "long": _num(latest.get(NC_LONG)),
            "short": _num(latest.get(NC_SHORT)),
            "net": nc_net,
            "net_change_1w": (nc_net - prev_nc_net) if (nc_net is not None and prev_nc_net is not None) else None,
            "range_1y": _range_stats(nc_net_series[-WEEKS_1Y:], nc_net) if nc_net is not None else None,
            "range_3y": _range_stats(nc_net_series[-WEEKS_3Y:], nc_net) if nc_net is not None else None,
        },
        "commercial": {
            "long": _num(latest.get(C_LONG)),
            "short": _num(latest.get(C_SHORT)),
            "net": c_net,
            "net_change_1w": (c_net - prev_c_net) if (c_net is not None and prev_c_net is not None) else None,
            "range_1y": _range_stats(c_net_series[-WEEKS_1Y:], c_net) if c_net is not None else None,
            "range_3y": _range_stats(c_net_series[-WEEKS_3Y:], c_net) if c_net is not None else None,
        },
        "non_reportable_net": nr_net,
        "trend": trend,
    }


def positioning(*, instrument: str | None = None, code: str | None = None) -> dict:
    """Summary for one contract by registry id/code or raw CFTC code."""
    if instrument:
        inst = reg.resolve(instrument)
        resolved = inst.meta.get("cot_code")
        if not resolved:
            raise ValueError(f"{inst.label} has no cot_code — set meta when adding or use cot_search")
    elif code:
        resolved = code
    else:
        raise ValueError("provide either instrument or code")

    summary = summarize(cot.cot_history(resolved))
    summary["cot_code"] = resolved
    return summary


def _one(inst: reg.TrackedInstrument) -> tuple[str, dict]:
    if not inst.meta.get("cot_code"):
        return inst.id, {
            "ok": False,
            "name": inst.label,
            "error": "no cot_code metadata — use cot_search to find the CFTC code",
        }
    try:
        return inst.id, {"ok": True, "name": inst.label, "code": inst.code, **positioning(code=inst.meta["cot_code"])}
    except Exception as exc:  # noqa: BLE001
        return inst.id, {
            "ok": False,
            "name": inst.label,
            "cot_code": inst.meta.get("cot_code"),
            "error": f"{type(exc).__name__}: {exc}"[:200],
        }


def dashboard() -> dict:
    """COT for all tracked futures that have a cot_code (sequential — CFTC rate limits)."""
    futures = [i for i in reg.list_all() if i.asset == "futures" and i.meta.get("cot_code")]
    if not futures:
        return {}
    return dict(_one(inst) for inst in futures)


def search(query: str) -> list[dict]:
    return cot.cot_search(query)
