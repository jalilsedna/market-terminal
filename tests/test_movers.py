"""Movers screener — Grouped Daily parse + compute (no network, runs in CI)."""

from __future__ import annotations


def test_parse_grouped_basic_and_skips_garbage():
    from obb_layer.grouped import parse_grouped

    results = [
        {"T": "AAPL", "o": 100, "h": 111, "l": 99, "c": 110, "v": 1000, "n": 50},
        {"T": "MSFT", "o": 200, "h": 205, "l": 188, "c": 190, "v": 2000, "n": 80},
        {"T": "BAD", "o": 1, "h": 3, "l": 0, "v": 5, "n": 1},          # missing 'c' → skipped
        {"T": "", "o": 5, "h": 5, "l": 5, "c": 5, "v": 5, "n": 1},     # empty ticker → skipped
    ]
    out = parse_grouped(results)
    assert set(out) == {"AAPL", "MSFT"}
    assert out["AAPL"]["close"] == 110.0
    assert out["MSFT"]["volume"] == 2000.0


def test_parse_grouped_handles_none():
    from obb_layer.grouped import parse_grouped

    assert parse_grouped(None) == {}


def test_compute_movers_ranks_and_filters():
    from services.movers import compute_movers

    today = {
        "GAIN": {"close": 120.0, "volume": 1_000_000},   # +20%
        "LOSE": {"close": 80.0, "volume": 1_000_000},    # -20%
        "ACTV": {"close": 100.0, "volume": 50_000_000},  # huge $vol
        "PENNY": {"close": 0.50, "volume": 100_000_000},   # below min_price → excluded
        "THIN": {"close": 100.0, "volume": 10},            # below $vol floor → excluded
        "NOPRV": {"close": 100.0, "volume": 1_000_000},    # not in prev → excluded
        "lower": {"close": 100.0, "volume": 1_000_000},    # non-plain ticker → excluded
        "BRK.B": {"close": 100.0, "volume": 1_000_000},    # has '.' → excluded
    }
    prev = {
        "GAIN": {"close": 100.0, "volume": 1},
        "LOSE": {"close": 100.0, "volume": 1},
        "ACTV": {"close": 100.0, "volume": 1},
        "PENNY": {"close": 0.40, "volume": 1},
        "THIN": {"close": 100.0, "volume": 1},
        "lower": {"close": 100.0, "volume": 1},
        "BRK.B": {"close": 100.0, "volume": 1},
    }
    out = compute_movers(today, prev, min_price=1.0, min_dollar_volume=5_000_000.0, top_n=10)

    tickers = {r["ticker"] for r in out["gainers"]} | {r["ticker"] for r in out["losers"]}
    assert "PENNY" not in tickers and "THIN" not in tickers
    assert "NOPRV" not in tickers and "lower" not in tickers and "BRK.B" not in tickers
    assert out["universe"] == 3  # GAIN, LOSE, ACTV
    assert out["gainers"][0]["ticker"] == "GAIN"
    assert out["gainers"][0]["change_1d_pct"] == 20.0
    assert out["losers"][0]["ticker"] == "LOSE"
    assert out["losers"][0]["change_1d_pct"] == -20.0
    assert out["most_active"][0]["ticker"] == "ACTV"


def test_compute_movers_top_n_caps():
    from services.movers import compute_movers

    # 50 distinct letters-only tickers ('AA'..'BX'), so the plain-symbol filter
    # keeps them all; dollar_volume ~100M clears the floor.
    tickers = [chr(65 + i // 26) + chr(65 + i % 26) for i in range(50)]
    today = {t: {"close": 100.0 + idx, "volume": 1_000_000} for idx, t in enumerate(tickers)}
    prev = {t: {"close": 100.0, "volume": 1} for t in tickers}
    out = compute_movers(today, prev, top_n=5)
    assert len(out["gainers"]) == 5
    assert len(out["losers"]) == 5
    assert len(out["most_active"]) == 5
