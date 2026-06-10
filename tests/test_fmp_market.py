"""FMP market symbol mapping — no network."""

from __future__ import annotations

from obb_layer.fmp_market import resolve_fmp_symbol


def test_futures_continuation_map():
    assert resolve_fmp_symbol("GC=F") == "GCUSD"
    assert resolve_fmp_symbol("NQ=F") == "^NDX"


def test_fx_proxy_strips_suffix():
    assert resolve_fmp_symbol("EURUSD=X") == "EURUSD"
