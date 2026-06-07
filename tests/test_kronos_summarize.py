"""Pure path-summarization logic for the forecasting layer.

`_summarize_paths` reduces sampled forecast paths to a median + close band. It is
numpy-only (no torch, no network), so it's covered here in the fast CI job — the
real model never runs in CI.
"""

from __future__ import annotations

import numpy as np
import pytest

from kronos_layer.forecast import _summarize_paths
from kronos_layer.types import OHLCV


def _paths(n_paths: int, horizon: int) -> np.ndarray:
    rng = np.random.default_rng(0)
    return rng.normal(100.0, 5.0, size=(n_paths, horizon, len(OHLCV)))


def test_shapes_and_metadata():
    r = _summarize_paths(_paths(20, 7), OHLCV)
    assert r.horizon == 7
    assert r.n_paths == 20
    assert r.columns == list(OHLCV)
    assert r.median.shape == (7, len(OHLCV))
    assert r.close_median().shape == (7,)


def test_median_matches_numpy():
    paths = _paths(11, 4)
    r = _summarize_paths(paths, OHLCV)
    assert np.allclose(r.median, np.median(paths, axis=0))


def test_close_band_is_monotone():
    r = _summarize_paths(_paths(50, 5), OHLCV)
    q = r.close_quantiles
    assert {0.1, 0.5, 0.9} <= set(q)
    assert np.all(q[0.1] <= q[0.5]) and np.all(q[0.5] <= q[0.9])


def test_rejects_non_3d():
    with pytest.raises(ValueError):
        _summarize_paths(np.zeros((3, 4)), OHLCV)


def test_requires_close_column():
    with pytest.raises(ValueError):
        _summarize_paths(np.zeros((2, 3, 2)), ["open", "high"])


def test_rejects_empty():
    with pytest.raises(ValueError):
        _summarize_paths(np.zeros((0, 5, len(OHLCV))), OHLCV)
