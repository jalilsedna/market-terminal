"""Volatility analysis — realized vol, regime, and short-horizon forecast (E3).

Works for any tracked instrument (futures, crypto, forex, equity, ETF).
Composes `obb_layer` OHLCV with the pure `vol/` library. Research context only.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from services import instruments as reg
from services.custom_watchlist import FETCHERS
from vol import ewma_vol, har_rv_forecast, log_returns, realized_vol_series, vol_regime

DISCLAIMER = (
    "Volatility estimate/forecast — research context only, not advice or a trade trigger."
)
_VOL_WINDOW = 21
_MIN_BARS = _VOL_WINDOW + 60


def _closes_for(inst: reg.TrackedInstrument):
    fetch = FETCHERS.get(inst.asset)
    if fetch is None:
        raise ValueError(f"no price fetcher for asset {inst.asset!r}")
    start = (date.today() - timedelta(days=365 * 3 + 10)).isoformat()
    records = fetch(inst.symbol, start_date=start)
    if not records:
        return None, None
    recs = sorted(records, key=lambda r: str(r.get("date", "")))
    close = np.array([float(r["close"]) for r in recs if r.get("close") is not None])
    return close, recs[-1].get("date")


def _read_from_closes(name: str, instrument: str, close, as_of, horizon: int) -> dict:
    base = {"instrument": instrument, "name": name, "disclaimer": DISCLAIMER}
    if close is None or len(close) < _MIN_BARS:
        return {**base, "ok": False, "error": "insufficient history (provider down / throttled?)"}
    try:
        rv = realized_vol_series(close, window=_VOL_WINDOW)
        current = float(rv[-1])
        regime = vol_regime(current, rv[:-1])
        ewma = ewma_vol(log_returns(close))
        har = float(np.mean(har_rv_forecast(rv, horizon)["forecast"]))
    except Exception as exc:  # noqa: BLE001
        return {**base, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:160]}
    read = (
        f"{name}: realized vol {current * 100:.1f}% annualized — "
        f"{regime['regime']} ({regime['percentile']:.0f}th pct of ~3y). "
        f"{horizon}-day forecast ~{ewma * 100:.1f}% (EWMA)."
    )
    return {
        **base,
        "ok": True,
        "as_of": as_of,
        "current_vol_annualized": round(current, 4),
        "regime": regime,
        "forecast": {"horizon_days": horizon, "ewma": round(ewma, 4), "har_rv": round(har, 4)},
        "read": read,
    }


def volatility(instrument: str, horizon: int = 5) -> dict:
    """Realized vol + regime + forecast for one tracked instrument (by id or code)."""
    inst = reg.resolve(instrument)
    close, as_of = _closes_for(inst)
    return _read_from_closes(inst.label, inst.id, close, as_of, horizon)


def dashboard(horizon: int = 5) -> dict:
    """Volatility read across every tracked instrument."""
    out: dict = {}
    for inst in reg.list_all():
        try:
            close, as_of = _closes_for(inst)
            out[inst.id] = _read_from_closes(inst.label, inst.id, close, as_of, horizon)
        except Exception as exc:  # noqa: BLE001
            out[inst.id] = {
                "instrument": inst.id,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}"[:160],
            }
    return {"instruments": out, "disclaimer": DISCLAIMER}
