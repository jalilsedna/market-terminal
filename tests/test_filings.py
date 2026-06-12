"""SEC filings (ROADMAP H4) — normalize + flag, no network."""

from __future__ import annotations

import pytest


def test_requires_ticker():
    from services import filings

    with pytest.raises(ValueError):
        filings.filings("")


def test_flag_material_forms():
    from services.filings import _flag

    assert _flag("8-K") == "material event"
    assert _flag("10-Q") == "quarterly report"
    assert _flag("4") == "insider transaction"
    assert _flag("SC 13D") == "activist stake"
    assert _flag("ARS") is None  # non-material → no flag


def test_filings_normalizes_and_flags(monkeypatch):
    import config
    from obb_layer import fmp
    from services import filings

    monkeypatch.setenv("FMP_API_KEY", "k")
    config.get_settings.cache_clear()
    monkeypatch.setattr(fmp, "sec_filings", lambda t, limit=25: [
        {"type": "8-K", "filingDate": "2026-06-11 16:00", "finalLink": "http://x/8k",
         "title": "Results of Operations"},
        {"type": "10-Q", "filingDate": "2026-05-01", "finalLink": "http://x/10q"},
        {"type": "ARS", "filingDate": "2026-04-01"},
    ])
    try:
        out = filings.filings("AAPL", limit=10)
        assert out["enabled"] is True and out["count"] == 3
        assert out["filings"][0]["form"] == "8-K"
        assert out["filings"][0]["flag"] == "material event"
        assert out["filings"][0]["url"] == "http://x/8k"
        assert out["filings"][2]["flag"] is None  # ARS not material
        assert out["material_count"] == 2  # 8-K + 10-Q
        assert out["errors"] is None
    finally:
        config.get_settings.cache_clear()


def test_filings_degrades_on_gated_endpoint(monkeypatch):
    import config
    from obb_layer import fmp
    from services import filings

    monkeypatch.setenv("FMP_API_KEY", "k")
    config.get_settings.cache_clear()

    def boom(t, limit=25):
        raise fmp.FmpError("sec-filings-search/symbol: HTTP 402")

    monkeypatch.setattr(fmp, "sec_filings", boom)
    try:
        out = filings.filings("AAPL")
        assert out["enabled"] is True            # didn't crash
        assert out["filings"] == [] and out["errors"] and "filings" in out["errors"]
    finally:
        config.get_settings.cache_clear()


def test_filings_no_key(monkeypatch):
    import config
    from services import filings

    monkeypatch.delenv("FMP_API_KEY", raising=False)
    config.get_settings.cache_clear()
    try:
        out = filings.filings("AAPL")
        assert out["enabled"] is False and "FMP" in out["error"]
    finally:
        config.get_settings.cache_clear()
