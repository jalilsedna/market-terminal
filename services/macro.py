"""V1 — Macro Dashboard domain logic (SPEC.md §4 V1).

Composes the `obb_layer.macro` data functions into the dashboard's panels and
computes derived metrics (% change over day/week/month, 2s10s spread, latest
tiles). Each panel is built independently and fault-tolerant: if a provider
fails or is unavailable, that panel returns `ok=False` with a reason and the
rest of the dashboard still renders (SPEC.md §6 — label availability explicitly,
never imply a tradeable signal).

Services never import OpenBB directly; they go through `obb_layer/`.
"""

from __future__ import annotations

from collections.abc import Callable

from concurrency import parallel_map
from obb_layer import macro

# Cash-index proxies behind the index futures the user trades (SPEC §4 V1).
INDEX_PROXIES = {
    "^GSPC": "S&P 500 (ES)",
    "^NDX": "Nasdaq-100 (NQ)",
    "^DJI": "Dow Jones (YM)",
}

# FRED series shown as macro tiles: id -> (label, unit).
MACRO_TILES = {
    "UNRATE": ("Unemployment rate", "%"),
    "CPIAUCSL": ("CPI (headline, YoY)", "% YoY"),
    "DGS10": ("10Y Treasury yield", "%"),
    "FEDFUNDS": ("Fed funds rate", "%"),
}


def _pct(latest: float | None, prior: float | None) -> float | None:
    if latest is None or prior in (None, 0):
        return None
    return round((latest - prior) / prior * 100, 2)


def _nth_back(values: list[float], n: int) -> float | None:
    """Value n steps before the last, or None if the series is too short."""
    return values[-1 - n] if len(values) > n else None


def _series_change(records: list[dict], value_key: str) -> dict:
    """Latest value + day/week/month change for an ordered (oldest→newest) series."""
    points = [(r.get("date"), r.get(value_key)) for r in records if r.get(value_key) is not None]
    if not points:
        raise ValueError("series has no usable values")
    values = [v for _, v in points]
    latest = values[-1]
    return {
        "as_of": str(points[-1][0])[:10],
        "value": round(float(latest), 4),
        "change_1d_pct": _pct(latest, _nth_back(values, 1)),
        "change_1w_pct": _pct(latest, _nth_back(values, 5)),
        "change_1m_pct": _pct(latest, _nth_back(values, 21)),
    }


def _fred_value_key(records: list[dict]) -> str:
    """The non-date column of a FRED series (named after the series id)."""
    for key in records[0]:
        if str(key).lower() not in ("date", "datetime", "index"):
            return key
    raise ValueError("no value column in FRED series")


def _panel(builder: Callable[[], dict], freshness: str) -> dict:
    """Run a panel builder, attaching freshness on success or a reason on failure."""
    try:
        data = builder()
        data.setdefault("ok", True)
        data["freshness"] = freshness
        return data
    except Exception as exc:  # noqa: BLE001 — one panel must not sink the dashboard
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}


# --- Panel builders ----------------------------------------------------------

def _rates_panel() -> dict:
    # federal_reserve returns rates as decimals (0.0449 = 4.49%). Normalize to
    # percent so the curve matches the FRED-sourced yield tile, and so 2s10s is
    # a correct basis-point spread. Field names carry the unit to avoid ambiguity.
    curve = macro.yield_curve()
    points = [
        {
            "maturity": r.get("maturity"),
            "years": r.get("maturity_years"),
            "rate_pct": round(float(r["rate"]) * 100, 3),
        }
        for r in curve
        if r.get("rate") is not None
    ]
    by_years = {round(float(p["years"]), 2): p["rate_pct"] for p in points if p.get("years") is not None}

    def nearest(target: float) -> float | None:
        if not by_years:
            return None
        yr = min(by_years, key=lambda y: abs(y - target))
        return by_years[yr] if abs(yr - target) <= 0.5 else None

    two, ten = nearest(2.0), nearest(10.0)
    # Both are in percent; (ten - two) is in percentage points × 100 -> basis points.
    spread = round((ten - two) * 100, 1) if (two is not None and ten is not None) else None
    return {
        "curve": points,
        "two_year_pct": two,
        "ten_year_pct": ten,
        "spread_2s10s_bps": spread,
        "curve_date": str(curve[-1].get("date"))[:10] if curve else None,
    }


def _dollar_fx_panel() -> dict:
    usd = macro.fred_series("DTWEXBGS")
    return {
        "dollar_index": {"series": "DTWEXBGS", **_series_change(usd, _fred_value_key(usd))},
        "eurusd": _series_change(macro.fx_history("EURUSD"), "close"),
        "gbpusd": _series_change(macro.fx_history("GBPUSD"), "close"),
    }


def _macro_tiles_panel() -> dict:
    tiles = []
    for series_id, (label, unit) in MACRO_TILES.items():
        try:
            records = macro.fred_series(series_id)
            key = _fred_value_key(records)
            values = [r.get(key) for r in records if r.get(key) is not None]
            latest = float(values[-1])
            # CPI as a level -> show year-over-year change instead of the index.
            if series_id == "CPIAUCSL":
                yoy = _pct(latest, _nth_back(values, 12))
                tiles.append({"label": label, "value": yoy, "unit": unit,
                              "as_of": str(records[-1].get("date"))[:10]})
            else:
                tiles.append({"label": label, "value": round(latest, 2), "unit": unit,
                              "as_of": str(records[-1].get("date"))[:10]})
        except Exception as exc:  # noqa: BLE001 — skip a tile, keep the rest
            tiles.append({"label": label, "value": None, "unit": unit,
                          "error": f"{type(exc).__name__}"})
    return {"tiles": tiles}


def _indices_panel() -> dict:
    out = {}
    for symbol, label in INDEX_PROXIES.items():
        try:
            out[symbol] = {"label": label, **_series_change(macro.index_history(symbol), "close")}
        except Exception as exc:  # noqa: BLE001
            out[symbol] = {"label": label, "ok": False, "error": f"{type(exc).__name__}"}
    return {"indices": out}


def _calendar_panel() -> dict:
    events = macro.economic_calendar(days_ahead=7)
    trimmed = [
        {k: ev.get(k) for k in ("date", "event", "country", "importance", "actual", "previous", "consensus")
         if k in ev}
        for ev in events
    ]
    return {"events": trimmed, "count": len(trimmed)}


def build_dashboard() -> dict:
    """Assemble the full V1 macro dashboard (all panels, each fault-tolerant).

    The five panels are built concurrently — each makes its own independent,
    network-bound provider calls.
    """
    specs = [
        ("rates", _rates_panel, "daily (latest session)"),
        ("dollar_fx", _dollar_fx_panel, "EOD / daily"),
        ("macro_tiles", _macro_tiles_panel, "FRED release cadence"),
        ("indices", _indices_panel, "EOD (daily)"),
        ("calendar", _calendar_panel, "upcoming 7 days"),
    ]
    built = parallel_map(lambda s: (s[0], _panel(s[1], s[2])), specs)
    return dict(built)
