"""Chart tab — TradingView symbol map + /chart/symbols (no OpenBB, runs in CI)."""

from __future__ import annotations

import re


def test_every_instrument_has_a_tv_symbol():
    from obb_layer.symbols import WATCHLIST

    # EXCHANGE:ROOT1! continuous-futures form, e.g. COMEX:GC1!, CME_MINI:NQ1!.
    pat = re.compile(r"^[A-Z_]+:[A-Z0-9]+!$")
    for code, inst in WATCHLIST.items():
        assert inst.tv_symbol, f"{code} missing tv_symbol"
        assert pat.match(inst.tv_symbol), f"{code} tv_symbol '{inst.tv_symbol}' not EXCHANGE:ROOT! form"


def test_tv_symbols_are_unique():
    from obb_layer.symbols import WATCHLIST

    syms = [i.tv_symbol for i in WATCHLIST.values()]
    assert len(syms) == len(set(syms))


def test_chart_symbols_endpoint_shape():
    from app.routers.chart import chart_symbols

    env = chart_symbols()
    assert env.ok is True
    assert env.provider == "tradingview"
    picks = env.data["picks"]
    assert len(picks) == 5  # the futures watchlist
    for p in picks:
        assert set(p) == {"code", "name", "tv_symbol"}
    # GC maps to COMEX gold continuous
    gc = next(p for p in picks if p["code"] == "GC")
    assert gc["tv_symbol"] == "COMEX:GC1!"
