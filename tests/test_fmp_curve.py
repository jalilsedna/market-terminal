"""FMP commodity curve builder — mocked, no network."""

from __future__ import annotations

from datetime import date

import pytest

from obb_layer.fmp_curve import expiration_from_trade_month


def test_expiration_rolls_year_when_month_passed():
    assert expiration_from_trade_month("Jan", ref=date(2026, 6, 1)) == "2027-01"


def test_expiration_unknown_month_raises():
    with pytest.raises(ValueError, match="unknown trade month"):
        expiration_from_trade_month("Qux")
