"""Volatility analysis — realized vol, regime, and a short-horizon forecast (E3).

The forecasting pillar, validated and shipped. Composes `obb_layer` OHLCV with the
pure `vol/` library (realized vol, HAR-RV, EWMA, regime). Research context only —
a vol/regime read for sizing/regime awareness, never a trade trigger.

Forecaster: **EWMA** (validated best on daily futures in `scripts/eval_vol.py`),
with HAR-RV reported alongside. Like the rest of the terminal, services call
`obb_layer/`, never OpenBB directly; failures degrade the read rather than raise.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from obb_layer.market import futures_history
from obb_layer.symbols import WATCHLIST
from vol import ewma_vol, har_rv_forecast, log_returns, realized_vol_series, vol_regime

DISCLAIMER = (
    "Volatility estimate/forecast — research context only, not advice or a trade trigger."
)
_VOL_WINDOW = 21  # trailing window for the realized-vol series
_MIN_BARS = _VOL_WINDOW + 60  # enough for a stable regime percentile + forecast


def _closes(instrument: str):
    """Return (Instrument, close-price ndarray | None, as_of) for a watchlist code.
    Pulls ~3y of daily history so the regime percentile and HAR have enough data."""
    inst = WATCHLIST.get(instrument)
    if inst is None:
        raise ValueError(f"unknown instrument {instrument!r}; choose from {list(WATCHLIST)}")
    start = (date.today() - timedelta(days=365 * 3 + 10)).isoformat()
    records = futures_history(inst.yf_symbol, start_date=start)
    if not records:
        return inst, None, None
    recs = sorted(records, key=lambda r: str(r.get("date", "")))
    close = np.array([float(r["close"]) for r in recs if r.get("close") is not None])
    return inst, close, recs[-1].get("date")


def volatility(instrument: str, horizon: int = 5) -> dict:
    """Realized vol + regime + short-horizon forecast for one watchlist instrument."""
    inst, close, as_of = _closes(instrument)
    base = {"instrument": instrument, "name": inst.name, "disclaimer": DISCLAIMER}
    if close is None or len(close) < _MIN_BARS:
        return {**base, "ok": False, "error": "insufficient history (provider down / throttled?)"}

    try:
        rv = realized_vol_series(close, window=_VOL_WINDOW)
        current = float(rv[-1])
        regime = vol_regime(current, rv[:-1])
        ewma = ewma_vol(log_returns(close))
        har = float(np.mean(har_rv_forecast(rv, horizon)["forecast"]))
    except Exception as exc:  # noqa: BLE001 — degrade rather than fail the view
        return {**base, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:160]}

    read = (
        f"{inst.name}: realized vol {current * 100:.1f}% annualized — "
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


def dashboard(horizon: int = 5) -> dict:
    """Volatility read across the whole futures watchlist."""
    out: dict = {}
    for code in WATCHLIST:
        try:
            out[code] = volatility(code, horizon)
        except Exception as exc:  # noqa: BLE001 — one instrument must not sink the dash
            out[code] = {"instrument": code, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:160]}
    return {"instruments": out, "disclaimer": DISCLAIMER}
