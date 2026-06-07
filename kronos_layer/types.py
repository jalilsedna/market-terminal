"""Typed forecast result + the forecasting disclaimer.

Deliberately numpy-only (no pandas/torch at module load) so this and the pure
summarization logic stay importable and testable without the heavy stack.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Shown with every forecast, everywhere it surfaces (REST / MCP / UI). A forecast
# is the closest thing to a signal the terminal will ever show, so it is framed
# as probabilistic research context — never advice or a trade trigger.
DISCLAIMER = (
    "Model-generated probabilistic forecast — research context only, not advice "
    "or a trade trigger; forecasts are uncertain and frequently wrong."
)

# Canonical OHLCV column order Kronos consumes/produces.
OHLCV = ("open", "high", "low", "close", "volume")


@dataclass
class ForecastResult:
    """A reduced, distribution-aware forecast for `horizon` future bars.

    `median` is the element-wise median OHLCV path across the sampled paths;
    `close_quantiles` carries the close-price uncertainty band (quantile → per-step
    series) that the UI renders as a cone.
    """

    horizon: int
    columns: list[str]                       # length == median.shape[1]
    median: np.ndarray                       # (horizon, n_features)
    close_quantiles: dict[float, np.ndarray]  # quantile -> (horizon,)
    n_paths: int
    disclaimer: str = DISCLAIMER

    def close_median(self) -> np.ndarray:
        """The median forecast close path (horizon,)."""
        return self.median[:, self.columns.index("close")]
