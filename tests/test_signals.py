"""Trade-setup signal scoring (ROADMAP H7) — pure logic, no network."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from services import signals as sig


def _recent(days_ago: int = 1) -> str:
    return (datetime.now(UTC).date() - timedelta(days=days_ago)).isoformat()


def test_trend_signal():
    assert sig.trend_signal(110, 100, 90) == (2, "uptrend (price > 50 & 200 MA)")
    assert sig.trend_signal(80, 100, 90)[0] == -2
    assert sig.trend_signal(95, 90, 100)[0] == 1   # above 50, below 200
    assert sig.trend_signal(95, 100, 90)[0] == -1  # below 50, above 200
    assert sig.trend_signal(None, 100, 90) == (0, "trend unknown")


def test_momentum_signal_bias_and_flags():
    pts, flags, detail = sig.momentum_signal(72, 30)
    assert pts == 1  # rsi > 55 bullish lean
    assert any("overbought" in f for f in flags)
    assert detail["trending"] is True
    pts2, flags2, detail2 = sig.momentum_signal(25, 15)
    assert pts2 == -1
    assert any("oversold" in f for f in flags2)
    assert detail2["trending"] is False
    assert any("choppy" in f for f in flags2)


def test_catalyst_signal_upgrade_and_pt_rising():
    grades = [
        {"analystRatingsStrongBuy": 10, "analystRatingsBuy": 8, "analystRatingsHold": 2,
         "analystRatingsSell": 0, "analystRatingsStrongSell": 0},  # now (net higher)
        {"analystRatingsStrongBuy": 6, "analystRatingsBuy": 8, "analystRatingsHold": 4,
         "analystRatingsSell": 1, "analystRatingsStrongSell": 0},  # prior
    ]
    pt = {"lastMonthAvgPriceTarget": 220, "lastQuarterAvgPriceTarget": 200}
    news = [{"publishedDate": _recent(1)}, {"publishedDate": _recent(2)}]
    earn = [{"date": (datetime.now(UTC).date() + timedelta(days=3)).isoformat()}]
    pts, trigs, detail = sig.catalyst_signal(grades, pt, news, earn)
    assert pts >= 2  # upgrade + PT rising
    assert any("upgrade" in t for t in trigs)
    assert any("price targets rising" in t for t in trigs)
    assert any("fresh headline" in t for t in trigs)
    assert detail["earnings"]["days_away"] == 3


def test_catalyst_signal_downgrade_and_pt_falling():
    grades = [
        {"strongBuy": 2, "buy": 4, "hold": 6, "sell": 5, "strongSell": 2},
        {"strongBuy": 6, "buy": 6, "hold": 4, "sell": 1, "strongSell": 0},
    ]
    pt = {"lastMonthAvgPriceTarget": 180, "lastQuarterAvgPriceTarget": 200}
    pts, trigs, _ = sig.catalyst_signal(grades, pt, [], [])
    assert pts <= -2
    assert any("downgrade" in t for t in trigs)
    assert any("price targets falling" in t for t in trigs)


def test_smart_money_signal_insider_and_congress():
    stats = [{"acquiredTransactions": 8, "disposedTransactions": 2}]
    senate = [{"transactionDate": _recent(5), "type": "Purchase"},
              {"transactionDate": _recent(6), "type": "Purchase"}]
    house = [{"transactionDate": _recent(7), "type": "Sale"}]
    pts, trigs, detail = sig.smart_money_signal(stats, [], senate, house)
    assert pts >= 2  # insider net buying + net congress buying
    assert detail["insider_buy_ratio"] == 0.8
    assert detail["congress_net_90d"] == 1  # 2 buys - 1 sale
    assert any("insiders net buying" in t for t in trigs)


def test_smart_money_net_selling():
    stats = [{"acquiredTransactions": 1, "disposedTransactions": 9}]
    pts, trigs, _ = sig.smart_money_signal(stats, [], [], [])
    assert pts == -1
    assert any("net selling" in t for t in trigs)


def test_participation_relative_volume_and_range():
    p = sig.participation(price=150, volume=3_000_000, avg_volume=1_000_000,
                          year_high=200, year_low=100)
    assert p["relative_volume"] == 3.0
    assert p["in_play"] is True
    assert p["range_position_52w"] == 0.5
    quiet = sig.participation(150, 500_000, 1_000_000, 200, 100)
    assert quiet["in_play"] is False


def test_fuse_long_short_neutral():
    long = sig.fuse((2, "uptrend"), (1, [], {}), (2, ["upgrade"], {}), (1, [], {}), 1)
    assert long["bias"] == "long" and long["score"] == 7 and long["conviction"] == "high"
    short = sig.fuse((-2, "downtrend"), (-1, [], {}), (-1, ["dg"], {}), (0, [], {}), 0)
    assert short["bias"] == "short" and short["score"] == -4
    flat = sig.fuse((1, "x"), (0, [], {}), (0, [], {}), (0, [], {}), 0)
    assert flat["bias"] == "neutral" and flat["conviction"] == "low"


def test_hitlist_candidates_dedupe_and_direction():
    movers = {
        "gainers": [{"ticker": "AAA", "change_1d_pct": 8.0, "dollar_volume": 9e8}],
        "losers": [{"ticker": "BBB", "change_1d_pct": -6.0, "dollar_volume": 5e8}],
        "most_active": [
            {"ticker": "AAA", "change_1d_pct": 8.0, "dollar_volume": 9e8},  # dupe
            {"ticker": "CCC", "change_1d_pct": -1.0, "dollar_volume": 2e9},
        ],
    }
    c = sig.hitlist_candidates(movers)
    by = {x["ticker"]: x for x in c}
    assert set(by) == {"AAA", "BBB", "CCC"}
    assert by["AAA"]["day_dir"] == "up"
    assert by["BBB"]["day_dir"] == "down"
    assert by["CCC"]["day_dir"] == "down"  # negative change → down


def test_score_candidate_confluence():
    up = sig.score_candidate(8.0, 1, 1)   # up move + positive catalyst/smart
    assert up["bias"] == "long" and up["confluence"] is True and up["score"] == 4
    down = sig.score_candidate(-6.0, -1, 0)
    assert down["bias"] == "short" and down["confluence"] is True
    divergent = sig.score_candidate(8.0, -1, -1)  # up move but bearish signals
    assert divergent["confluence"] is False and divergent["bias"] == "neutral"


def test_rank_hitlist_orders_confluence_then_conviction():
    rows = [
        {"ticker": "LOW", "score": 2, "confluence": False, "change_1d_pct": 3},
        {"ticker": "TOP", "score": 4, "confluence": True, "change_1d_pct": 5},
        {"ticker": "MID", "score": 2, "confluence": True, "change_1d_pct": 9},
    ]
    ranked = sig.rank_hitlist(rows)
    assert [r["ticker"] for r in ranked] == ["TOP", "MID", "LOW"]


def test_daily_hitlist_composition(monkeypatch):
    from obb_layer import fmp
    from services import movers as movers_svc
    import config

    monkeypatch.setenv("FMP_API_KEY", "k")
    config.get_settings.cache_clear()

    monkeypatch.setattr(movers_svc, "movers", lambda top_n=25: {
        "as_of": "2026-06-10",
        "gainers": [{"ticker": "AAA", "change_1d_pct": 9.0, "dollar_volume": 9e8}],
        "losers": [{"ticker": "BBB", "change_1d_pct": -7.0, "dollar_volume": 6e8}],
        "most_active": [{"ticker": "CCC", "change_1d_pct": 0.5, "dollar_volume": 2e9}],
    })
    # AAA: bullish catalyst; BBB: nothing; CCC below min_move filtered out.
    def grades(t, limit=6):
        if t == "AAA":
            return [
                {"analystRatingsStrongBuy": 9, "analystRatingsBuy": 6, "analystRatingsHold": 1,
                 "analystRatingsSell": 0, "analystRatingsStrongSell": 0},
                {"analystRatingsStrongBuy": 5, "analystRatingsBuy": 6, "analystRatingsHold": 3,
                 "analystRatingsSell": 1, "analystRatingsStrongSell": 0},
            ]
        return []
    monkeypatch.setattr(fmp, "grades_historical", grades)
    monkeypatch.setattr(fmp, "earnings", lambda t, **k: [])
    monkeypatch.setattr(fmp, "insider_statistics", lambda t: [])

    try:
        out = sig.daily_hitlist(limit=10, min_move_pct=2.0)
        assert out["enabled"] is True
        tickers = [r["ticker"] for r in out["hitlist"]]
        assert "AAA" in tickers and "BBB" in tickers
        assert "CCC" not in tickers  # 0.5% move below min_move_pct
        aaa = next(r for r in out["hitlist"] if r["ticker"] == "AAA")
        assert aaa["bias"] == "long" and aaa["confluence"] is True
        assert out["hitlist"][0]["ticker"] == "AAA"  # confluence ranks first
    finally:
        config.get_settings.cache_clear()


def test_daily_hitlist_degrades_without_movers(monkeypatch):
    from services import movers as movers_svc
    import config

    monkeypatch.setenv("FMP_API_KEY", "k")
    config.get_settings.cache_clear()

    def boom(top_n=25):
        raise RuntimeError("no polygon key")
    monkeypatch.setattr(movers_svc, "movers", boom)
    try:
        out = sig.daily_hitlist()
        assert out["hitlist"] == []
        assert "movers feed unavailable" in out["error"]
    finally:
        config.get_settings.cache_clear()


def test_trade_setup_degrades_without_key(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    import config

    config.get_settings.cache_clear()
    try:
        out = sig.trade_setup("AAPL")
        assert out["enabled"] is False
        assert "FMP" in out["error"]
    finally:
        config.get_settings.cache_clear()


def test_trade_setup_composition(monkeypatch):
    """End-to-end composition with all FMP calls mocked (no network)."""
    from obb_layer import fmp
    import config

    monkeypatch.setenv("FMP_API_KEY", "test-key")
    config.get_settings.cache_clear()

    monkeypatch.setattr(fmp, "quote", lambda s: [{
        "symbol": s, "price": 150, "priceAvg50": 140, "priceAvg200": 120,
        "volume": 3_000_000, "avgVolume": 1_000_000, "yearHigh": 200, "yearLow": 100,
    }])
    monkeypatch.setattr(fmp, "technical_indicator",
                        lambda s, ind, **k: [{"rsi": 65, "adx": 30}] if ind in ("rsi", "adx") else [])
    monkeypatch.setattr(fmp, "grades_historical", lambda s, limit=6: [
        {"analystRatingsStrongBuy": 10, "analystRatingsBuy": 8, "analystRatingsHold": 2,
         "analystRatingsSell": 0, "analystRatingsStrongSell": 0},
        {"analystRatingsStrongBuy": 6, "analystRatingsBuy": 8, "analystRatingsHold": 4,
         "analystRatingsSell": 1, "analystRatingsStrongSell": 0},
    ])
    monkeypatch.setattr(fmp, "price_target_summary", lambda s: [
        {"lastMonthAvgPriceTarget": 220, "lastQuarterAvgPriceTarget": 200}])
    monkeypatch.setattr(fmp, "stock_news", lambda s, limit=10: [])
    monkeypatch.setattr(fmp, "earnings", lambda s, **k: [])
    monkeypatch.setattr(fmp, "insider_statistics", lambda s: [
        {"acquiredTransactions": 8, "disposedTransactions": 2}])
    monkeypatch.setattr(fmp, "insider_search", lambda s, limit=30: [])
    monkeypatch.setattr(fmp, "senate_trades", lambda s: [])
    monkeypatch.setattr(fmp, "house_trades", lambda s: [])
    monkeypatch.setattr(sig, "_context_lean", lambda s: (1, "constructive context"))

    try:
        out = sig.trade_setup("AAPL")
        assert out["enabled"] is True
        assert out["bias"] == "long"
        assert out["in_play"] is True
        assert out["participation"]["relative_volume"] == 3.0
        assert out["errors"] is None
        assert "AAPL" in out["read"]
    finally:
        config.get_settings.cache_clear()
