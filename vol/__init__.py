"""vol — realized-volatility analytics + forecasting (pure numpy, no torch).

The forecasting pillar, pivoted from price/direction (which no open model beats
persistence at — see docs/decisions.md §E) to **volatility**, the one place these
methods have proven, defensible skill. HAR-RV is the academic workhorse; it needs
no foundation model and runs in-core (no separate service), so unlike Kronos this
ships in the lean terminal itself.

Everything here is pure (OHLCV arrays in, numbers out) and unit-tested. A future
`services/volatility.py` composes these with `obb_layer` data; this package has no
I/O and no heavy deps.
"""

from __future__ import annotations

from vol.forecast import ewma_vol, har_rv_forecast, persistence_forecast
from vol.realized import (
    close_to_close_vol,
    daily_vol_series,
    garman_klass_vol,
    log_returns,
    parkinson_vol,
)
from vol.regime import vol_regime
from vol.score import mae, qlike, rmse

__all__ = [
    "log_returns",
    "close_to_close_vol",
    "parkinson_vol",
    "garman_klass_vol",
    "daily_vol_series",
    "ewma_vol",
    "har_rv_forecast",
    "persistence_forecast",
    "vol_regime",
    "rmse",
    "mae",
    "qlike",
]
