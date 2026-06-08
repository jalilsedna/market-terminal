"""Realized-volatility estimators from OHLCV (annualized, pure numpy).

All return **annualized** volatility (a standard deviation of returns × √periods),
so numbers are comparable across instruments and to implied vol. Range-based
estimators (Parkinson, Garman-Klass) use the high/low/open and are several times
more statistically efficient than close-to-close for the same window.
"""

from __future__ import annotations

import numpy as np

TRADING_DAYS = 252  # annualization factor for daily bars


def log_returns(close) -> np.ndarray:
    """Log returns of a close series (length N-1)."""
    c = np.asarray(close, dtype=float)
    if c.ndim != 1 or len(c) < 2:
        raise ValueError("close must be 1-D with >= 2 points")
    if np.any(c <= 0):
        raise ValueError("close must be positive")
    return np.diff(np.log(c))


def close_to_close_vol(close, window: int = 21, annualize: int = TRADING_DAYS) -> float:
    """Annualized close-to-close realized vol over the last `window` returns."""
    r = log_returns(close)
    if len(r) < window:
        raise ValueError(f"need >= {window} returns, got {len(r)}")
    return float(np.std(r[-window:], ddof=1) * np.sqrt(annualize))


def parkinson_vol(high, low, window: int = 21, annualize: int = TRADING_DAYS) -> float:
    """Annualized Parkinson (1980) high-low range vol over the last `window` bars."""
    h = np.asarray(high, dtype=float)[-window:]
    low_ = np.asarray(low, dtype=float)[-window:]
    if len(h) < window:
        raise ValueError(f"need >= {window} bars, got {len(h)}")
    hl = np.log(h / low_)
    var = np.mean(hl**2) / (4.0 * np.log(2.0))
    return float(np.sqrt(var * annualize))


def garman_klass_vol(
    open_, high, low, close, window: int = 21, annualize: int = TRADING_DAYS
) -> float:
    """Annualized Garman-Klass OHLC vol over the last `window` bars (uses the full
    bar, so it's more efficient than close-to-close)."""
    o = np.asarray(open_, dtype=float)[-window:]
    h = np.asarray(high, dtype=float)[-window:]
    low_ = np.asarray(low, dtype=float)[-window:]
    c = np.asarray(close, dtype=float)[-window:]
    if len(o) < window:
        raise ValueError(f"need >= {window} bars, got {len(o)}")
    var = np.mean(0.5 * np.log(h / low_) ** 2 - (2 * np.log(2) - 1) * np.log(c / o) ** 2)
    return float(np.sqrt(max(var, 0.0) * annualize))


def daily_vol_series(open_, high, low, close, annualize: int = TRADING_DAYS) -> np.ndarray:
    """Per-bar annualized Garman-Klass vol — the daily realized-vol proxy the
    HAR-RV forecaster regresses on (one vol number per OHLC bar)."""
    o = np.asarray(open_, dtype=float)
    h = np.asarray(high, dtype=float)
    low_ = np.asarray(low, dtype=float)
    c = np.asarray(close, dtype=float)
    if not (len(o) == len(h) == len(low_) == len(c)) or len(o) < 1:
        raise ValueError("OHLC arrays must be equal length and non-empty")
    var = 0.5 * np.log(h / low_) ** 2 - (2 * np.log(2) - 1) * np.log(c / o) ** 2
    return np.sqrt(np.clip(var, 0.0, None) * annualize)
