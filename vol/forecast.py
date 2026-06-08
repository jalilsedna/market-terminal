"""Volatility forecasting — HAR-RV (the workhorse) + EWMA & persistence baselines.

HAR-RV (Corsi, 2009) regresses tomorrow's realized vol on its daily, weekly
(5-bar mean), and monthly (22-bar mean) history — a simple linear model that is
hard to beat on realized-vol forecasting and is the standard academic benchmark.
Multi-step forecasts iterate the one-step model forward. Pure numpy; no MLE, no
heavy deps.

Baselines mirror the Kronos eval's discipline: a forecast only earns its keep if
it beats **persistence** (tomorrow's vol = today's) and **EWMA** (RiskMetrics).
"""

from __future__ import annotations

import numpy as np


def _trailing_mean(x: np.ndarray, w: int) -> np.ndarray:
    """Trailing mean over window `w`; entries before a full window are NaN."""
    cs = np.cumsum(np.insert(x, 0, 0.0))
    out = np.full(len(x), np.nan)
    if len(x) >= w:
        out[w - 1 :] = (cs[w:] - cs[: len(x) - w + 1]) / w
    return out


def har_rv_forecast(vol_series, horizon: int = 5) -> dict:
    """Fit HAR-RV on a daily vol series and forecast `horizon` steps ahead.

    Returns {"forecast": (horizon,), "beta": (4,) [const, daily, weekly, monthly]}.
    Forecasts are clipped to be non-negative (vol can't go below zero).
    """
    v = np.asarray(vol_series, dtype=float)
    if len(v) < 30:
        raise ValueError(f"HAR-RV needs >= 30 observations, got {len(v)}")

    weekly = _trailing_mean(v, 5)
    monthly = _trailing_mean(v, 22)
    y = v[1:]  # predict next bar
    xd, xw, xm = v[:-1], weekly[:-1], monthly[:-1]
    valid = ~np.isnan(xw) & ~np.isnan(xm)
    y, xd, xw, xm = y[valid], xd[valid], xw[valid], xm[valid]

    X = np.column_stack([np.ones_like(xd), xd, xw, xm])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)

    # Iterate the one-step model forward, feeding forecasts back as history.
    hist = list(v)
    preds = []
    for _ in range(horizon):
        d = hist[-1]
        w = float(np.mean(hist[-5:]))
        m = float(np.mean(hist[-22:]))
        nxt = float(beta @ np.array([1.0, d, w, m]))
        nxt = max(nxt, 0.0)
        preds.append(nxt)
        hist.append(nxt)
    return {"forecast": np.array(preds), "beta": beta}


def ewma_vol(returns, lam: float = 0.94, annualize: int = 252) -> float:
    """RiskMetrics EWMA annualized vol (λ=0.94 is the daily default). Baseline."""
    r = np.asarray(returns, dtype=float)
    if len(r) < 1:
        raise ValueError("need at least one return")
    var = r[0] ** 2
    for x in r[1:]:
        var = lam * var + (1.0 - lam) * x**2
    return float(np.sqrt(var * annualize))


def persistence_forecast(vol_series, horizon: int = 5) -> np.ndarray:
    """Naive baseline: tomorrow's vol = today's, flat for `horizon` steps."""
    v = np.asarray(vol_series, dtype=float)
    if len(v) < 1:
        raise ValueError("empty series")
    return np.full(horizon, float(v[-1]))
