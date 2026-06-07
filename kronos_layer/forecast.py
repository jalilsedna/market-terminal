"""Forecasting entry point + the pure path-summarization logic.

`_summarize_paths` is deliberately separated from the model call: it is pure
numpy (no torch, no network), so the reduction from sampled paths → median +
quantile band is unit-tested without the heavy stack. `forecast` wires the real
Kronos predictor (lazy-imported via `client`) to that reducer.
"""

from __future__ import annotations

import numpy as np

from kronos_layer.types import OHLCV, ForecastResult

DEFAULT_QUANTILES = (0.1, 0.25, 0.5, 0.75, 0.9)


def _summarize_paths(
    paths,
    columns,
    *,
    quantiles=DEFAULT_QUANTILES,
    close_col: str = "close",
) -> ForecastResult:
    """Reduce sampled forecast paths to a median path + close-price band.

    `paths` is array-like of shape (n_paths, horizon, n_features); `columns` names
    the feature axis. Pure and side-effect free.
    """
    arr = np.asarray(paths, dtype=float)
    if arr.ndim != 3:
        raise ValueError(f"paths must be 3-D (n_paths, horizon, n_features); got {arr.shape}")
    n_paths, horizon, n_features = arr.shape
    cols = [str(c).lower() for c in columns]
    if len(cols) != n_features:
        raise ValueError(f"columns ({len(cols)}) != n_features ({n_features})")
    if close_col not in cols:
        raise ValueError(f"{close_col!r} not in columns {cols}")
    if n_paths == 0:
        raise ValueError("need at least one path to summarize")

    close_idx = cols.index(close_col)
    median = np.median(arr, axis=0)  # (horizon, n_features)
    close_band = {
        float(q): np.quantile(arr[:, :, close_idx], q, axis=0) for q in quantiles
    }
    return ForecastResult(
        horizon=horizon,
        columns=cols,
        median=median,
        close_quantiles=close_band,
        n_paths=n_paths,
    )


def forecast(
    df,
    x_timestamp,
    y_timestamp,
    *,
    horizon: int | None = None,
    samples: int | None = None,
    temperature: float = 1.0,
    top_p: float = 0.9,
) -> ForecastResult:
    """Forecast the next `horizon` bars for an OHLCV `df`.

    Draws `samples` independent paths from Kronos and reduces them to a median +
    band. `df` must carry the OHLCV columns; `x_timestamp`/`y_timestamp` are the
    context and future timestamp series (Kronos's API). Requires the forecasting
    stack — see `client.get_predictor`.
    """
    from config import get_settings  # local: keep config import cheap at module load
    from kronos_layer.client import get_predictor

    settings = get_settings()
    horizon = horizon or settings.kronos_horizon_default
    samples = samples or settings.kronos_samples

    predictor = get_predictor()
    ohlcv = list(OHLCV)
    paths = []
    for _ in range(samples):
        pred_df = predictor.predict(
            df=df,
            x_timestamp=x_timestamp,
            y_timestamp=y_timestamp,
            pred_len=horizon,
            T=temperature,
            top_p=top_p,
            sample_count=1,
        )
        # Select OHLCV (case-insensitively) in canonical order.
        lower = {str(c).lower(): c for c in pred_df.columns}
        paths.append(pred_df[[lower[c] for c in ohlcv]].to_numpy(dtype=float))

    return _summarize_paths(np.stack(paths), ohlcv)
