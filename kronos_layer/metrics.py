"""Pure forecast scoring + naive baselines (numpy only — no torch, no network).

Separated from the model run so the metrics that decide the §E gate are
unit-tested, and so a forecast can always be judged against the honest baselines:
*does Kronos beat predicting last-price-flat (persistence) on error, and beat a
coin flip / always-up on direction?* A low MAPE alone is meaningless on a flat
series — only "beats persistence" is.
"""

from __future__ import annotations

import numpy as np


def mae(forecast: np.ndarray, actual: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(forecast) - np.asarray(actual))))


def mape(forecast: np.ndarray, actual: np.ndarray) -> float:
    forecast, actual = np.asarray(forecast, float), np.asarray(actual, float)
    return float(np.mean(np.abs((forecast - actual) / actual)) * 100)


def _direction(path: np.ndarray, last_close: float) -> np.ndarray:
    """Step-to-step sign of a close path, seeded with the last context close."""
    return np.sign(np.diff(np.concatenate([[last_close], np.asarray(path, float)])))


def directional_hit(forecast_close: np.ndarray, actual_close: np.ndarray, last_close: float) -> float:
    """% of steps where the forecast got the up/down direction right."""
    f = _direction(forecast_close, last_close)
    a = _direction(actual_close, last_close)
    return float(np.mean(f == a) * 100)


def majority_up_rate(actual_close: np.ndarray, last_close: float) -> float:
    """The 'always predict up' hit-rate — the directional baseline to beat
    (a trending series can make 50% look easy)."""
    a = _direction(actual_close, last_close)
    return float(np.mean(a > 0) * 100)


def band_coverage(actual_close: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    """% of actuals falling inside the [lo, hi] band (target ≈ 80% for p10–p90)."""
    actual_close = np.asarray(actual_close, float)
    inside = (actual_close >= np.asarray(lo, float)) & (actual_close <= np.asarray(hi, float))
    return float(np.mean(inside) * 100)


def persistence_close(last_close: float, horizon: int) -> np.ndarray:
    """Naive baseline: predict the last close, flat, for `horizon` bars."""
    return np.full(horizon, float(last_close), dtype=float)


def aggregate(window_scores: list[dict]) -> dict:
    """Mean ± std across walk-forward windows for each metric key."""
    if not window_scores:
        raise ValueError("no window scores to aggregate")
    keys = window_scores[0].keys()
    out: dict = {}
    for k in keys:
        vals = np.array([w[k] for w in window_scores], dtype=float)
        out[k] = {"mean": float(np.mean(vals)), "std": float(np.std(vals))}
    return out
