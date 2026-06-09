"""Movers screener — Flat Files parse + compute (no S3/boto3, runs in CI)."""

from __future__ import annotations

import gzip


def _gz(csv_text: str) -> bytes:
    return gzip.compress(csv_text.encode("utf-8"))


def test_parse_day_aggs_basic_and_skips_garbage():
    from obb_layer.flatfiles import parse_day_aggs

    csv_text = (
        "ticker,volume,open,close,high,low,window_start,transactions\n"
        "AAPL,1000,100,110,111,99,1700000000000000000,50\n"
        "MSFT,2000,200,190,205,188,1700000000000000000,80\n"
        "BAD,notanumber,1,2,3,0,1700000000000000000,1\n"   # bad volume → skipped
        ",5,5,5,5,5,1700000000000000000,1\n"               # empty ticker → skipped
    )
    out = parse_day_aggs(_gz(csv_text))
    assert set(out) == {"AAPL", "MSFT"}
    assert out["AAPL"]["close"] == 110.0
    assert out["MSFT"]["volume"] == 2000.0


def test_date_from_key():
    from obb_layer.flatfiles import date_from_key

    assert date_from_key("us_stocks_sip/day_aggs_v1/2026/06/2026-06-08.csv.gz") == "2026-06-08"


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
