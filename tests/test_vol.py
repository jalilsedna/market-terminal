"""Volatility analytics — realized estimators, HAR-RV forecast, regime.

Pure numpy, validated against known answers on synthetic data (runs in CI).
"""

from __future__ import annotations

import numpy as np
import pytest

from vol import forecast as F
from vol import realized as R
from vol.regime import vol_regime


def _gbm_close(sigma_daily: float, n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0, sigma_daily, size=n)
    return 100.0 * np.exp(np.cumsum(r))


# --- realized estimators -------------------------------------------------- #
def test_close_to_close_recovers_known_vol():
    sigma = 0.01  # 1% daily
    close = _gbm_close(sigma, 400, seed=1)
    annual = R.close_to_close_vol(close, window=252)
    true = sigma * np.sqrt(252)
    assert 0.8 * true <= annual <= 1.2 * true


def test_log_returns_validation():
    assert len(R.log_returns([100, 101, 102])) == 2
    with pytest.raises(ValueError):
        R.log_returns([100])
    with pytest.raises(ValueError):
        R.log_returns([100, -1])


def test_range_estimators_positive():
    close = _gbm_close(0.012, 100, seed=2)
    high = close * 1.005
    low = close * 0.995
    open_ = close * 1.001
    assert R.parkinson_vol(high, low, window=21) > 0
    assert R.garman_klass_vol(open_, high, low, close, window=21) > 0
    series = R.daily_vol_series(open_, high, low, close)
    assert len(series) == len(close)
    assert np.all(series >= 0)


# --- HAR-RV forecast ------------------------------------------------------ #
def test_har_constant_series():
    v = np.full(120, 0.20)
    out = F.har_rv_forecast(v, horizon=5)
    assert out["beta"].shape == (4,)
    assert np.allclose(out["forecast"], 0.20, atol=1e-3)


def test_har_shapes_and_nonnegative():
    rng = np.random.default_rng(3)
    v = np.abs(0.2 + 0.05 * rng.standard_normal(200))  # positive vol-like series
    out = F.har_rv_forecast(v, horizon=10)
    assert out["forecast"].shape == (10,)
    assert np.all(out["forecast"] >= 0) and np.all(np.isfinite(out["forecast"]))


def test_har_needs_enough_data():
    with pytest.raises(ValueError):
        F.har_rv_forecast(np.ones(10))


# --- baselines ------------------------------------------------------------ #
def test_ewma_constant_magnitude():
    r = np.array([0.01, -0.01] * 100)
    assert F.ewma_vol(r) == pytest.approx(0.01 * np.sqrt(252), rel=0.05)


def test_persistence_is_flat_last():
    assert np.array_equal(F.persistence_forecast([0.1, 0.2, 0.3], 4), np.full(4, 0.3))


# --- regime --------------------------------------------------------------- #
def test_vol_regime_buckets():
    hist = np.linspace(0.1, 0.3, 101)  # 0.10 … 0.30
    assert vol_regime(0.12, hist)["regime"] == "calm"
    assert vol_regime(0.20, hist)["regime"] == "normal"
    assert vol_regime(0.295, hist)["regime"] == "stressed"
    out = vol_regime(0.20, hist)
    assert 45 <= out["percentile"] <= 55  # 0.20 is the median
