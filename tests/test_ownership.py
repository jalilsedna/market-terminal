"""Smart Money / Ownership (ROADMAP H3) — interpreted read, no network."""

from __future__ import annotations

import pytest


def test_requires_ticker():
    from services import ownership

    with pytest.raises(ValueError):
        ownership.ownership("")


def test_txn_side_classification():
    from services.ownership import _txn_side

    assert _txn_side("P-Purchase") == "buy"
    assert _txn_side("S-Sale") == "sell"
    assert _txn_side("Purchase") == "buy"
    assert _txn_side("gift") == "—"


def _patch(monkeypatch, *, stats, search, senate, house):
    import config
    from obb_layer import fmp
    monkeypatch.setenv("FMP_API_KEY", "k")
    config.get_settings.cache_clear()
    monkeypatch.setattr(fmp, "insider_statistics", lambda t: stats)
    monkeypatch.setattr(fmp, "insider_search", lambda t, limit=20: search)
    monkeypatch.setattr(fmp, "senate_trades", lambda t: senate)
    monkeypatch.setattr(fmp, "house_trades", lambda t: house)


def test_ownership_net_buying(monkeypatch):
    import config
    from services import ownership

    _patch(
        monkeypatch,
        stats=[{"acquiredTransactions": 8, "disposedTransactions": 2}],  # 0.8 ratio → +1
        search=[{"transactionDate": "2026-06-10", "reportingName": "CEO Jane",
                 "transactionType": "P-Purchase", "securitiesTransacted": 1000, "price": 50}],
        senate=[{"transactionDate": "2026-06-09", "lastName": "Smith", "type": "Purchase"}],
        house=[],
    )
    try:
        out = ownership.ownership("AAPL")
        assert out["enabled"] is True
        assert out["smart_money"]["lean"] == "buying"
        assert out["smart_money"]["insider_buy_ratio"] == 0.8
        assert out["insider_recent"][0]["side"] == "buy"
        assert out["insider_recent"][0]["value"] == 50000  # 1000 * 50
        assert out["congress_recent"][0]["chamber"] == "Senate"
        assert out["errors"] is None
    finally:
        config.get_settings.cache_clear()


def test_ownership_net_selling(monkeypatch):
    import config
    from services import ownership

    _patch(
        monkeypatch,
        stats=[{"acquiredTransactions": 1, "disposedTransactions": 9}],  # 0.1 ratio → -1
        search=[{"transactionDate": "2026-06-10", "reportingName": "CFO Bob",
                 "transactionType": "S-Sale", "securitiesTransacted": 500}],
        senate=[], house=[],
    )
    try:
        out = ownership.ownership("NVDA")
        assert out["smart_money"]["lean"] == "selling"
        assert out["insider_recent"][0]["side"] == "sell"
    finally:
        config.get_settings.cache_clear()


def test_ownership_degrades_on_partial_failure(monkeypatch):
    import config
    from obb_layer import fmp
    from services import ownership

    monkeypatch.setenv("FMP_API_KEY", "k")
    config.get_settings.cache_clear()
    monkeypatch.setattr(fmp, "insider_statistics", lambda t: [{"acquiredTransactions": 5, "disposedTransactions": 5}])
    monkeypatch.setattr(fmp, "insider_search", lambda t, limit=20: [])

    def boom(t):
        raise fmp.FmpError("senate-trades: HTTP 402")

    monkeypatch.setattr(fmp, "senate_trades", boom)
    monkeypatch.setattr(fmp, "house_trades", lambda t: [])
    try:
        out = ownership.ownership("MSFT")
        assert out["enabled"] is True
        assert out["errors"] and "senate" in out["errors"]  # surfaced, not crashed
        assert out["smart_money"]["lean"] == "neutral"  # 0.5 ratio, no congress
    finally:
        config.get_settings.cache_clear()


def test_ownership_no_key(monkeypatch):
    import config
    from services import ownership

    monkeypatch.delenv("FMP_API_KEY", raising=False)
    config.get_settings.cache_clear()
    try:
        out = ownership.ownership("AAPL")
        assert out["enabled"] is False and "FMP" in out["error"]
    finally:
        config.get_settings.cache_clear()
