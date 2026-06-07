"""Pure forecast-scoring metrics (numpy only — runs in the fast CI job)."""

from __future__ import annotations

import numpy as np
import pytest

from kronos_layer import metrics as M


def test_mae_mape():
    assert M.mae([10, 20], [10, 22]) == 1.0
    assert M.mape([100, 100], [100, 200]) == pytest.approx((0 + 0.5) / 2 * 100)


def test_directional_hit():
    # last=100; fc dirs (+,+,-); actual dirs (+,-,+) → 1/3 match
    hit = M.directional_hit([101, 102, 101], [101, 100, 101], last_close=100)
    assert hit == pytest.approx(100 / 3)


def test_majority_up_rate():
    # last=100; actual [101,102,101] → dirs (+,+,-) → 2/3 up
    assert M.majority_up_rate([101, 102, 101], last_close=100) == pytest.approx(200 / 3)


def test_band_coverage():
    cov = M.band_coverage([100, 200, 300], lo=[90, 90, 90], hi=[150, 150, 350])
    assert cov == pytest.approx(200 / 3)


def test_persistence_close():
    assert np.array_equal(M.persistence_close(100.0, 3), np.array([100.0, 100.0, 100.0]))


def test_aggregate_mean_std():
    agg = M.aggregate([{"a": 10.0}, {"a": 20.0}])
    assert agg["a"]["mean"] == 15.0
    assert agg["a"]["std"] == 5.0


def test_aggregate_empty_raises():
    with pytest.raises(ValueError):
        M.aggregate([])
