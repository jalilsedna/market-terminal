"""Forecast-scoring losses for the volatility eval (pure numpy, CI-tested).

RMSE/MAE are intuitive; **QLIKE** is the standard robust loss for *volatility*
forecasts (Patton 2011) — it's a proper scoring rule on variance, far less
sensitive to noisy vol proxies than squared error, so it's the one we judge on.
Lower is better for all three; HAR-RV must beat the EWMA and persistence
baselines on QLIKE to earn its keep.
"""

from __future__ import annotations

import numpy as np


def rmse(forecast, actual) -> float:
    f, a = np.asarray(forecast, float), np.asarray(actual, float)
    return float(np.sqrt(np.mean((f - a) ** 2)))


def mae(forecast, actual) -> float:
    f, a = np.asarray(forecast, float), np.asarray(actual, float)
    return float(np.mean(np.abs(f - a)))


def qlike(forecast_vol, actual_vol) -> float:
    """QLIKE loss on variance: mean(a/f - ln(a/f) - 1), with a,f = vol². Zero when
    forecast == actual, positive otherwise; the standard robust vol-forecast loss."""
    f = np.clip(np.asarray(forecast_vol, float) ** 2, 1e-12, None)
    a = np.clip(np.asarray(actual_vol, float) ** 2, 1e-12, None)
    return float(np.mean(a / f - np.log(a / f) - 1.0))
