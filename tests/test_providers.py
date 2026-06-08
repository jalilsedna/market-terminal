"""EOD provider-fallback chain (ROADMAP B4) — pure logic, no OpenBB."""

from __future__ import annotations

import pytest

from obb_layer import providers


@pytest.fixture(autouse=True)
def _identity_to_records(monkeypatch):
    # Bypass OBBject normalization; let routes return record-lists directly.
    monkeypatch.setattr(providers, "to_records", lambda obj, **k: obj)


def test_uses_first_provider_that_returns_rows():
    def route(provider=None, **kw):
        if provider == "a":
            raise RuntimeError("a is down")  # error → skip
        if provider == "b":
            return []  # empty → skip
        if provider == "c":
            return [{"date": "d", "close": 1.0}]
        return []

    assert providers.eod_with_fallback(route, "SYM", providers=["a", "b", "c"]) == [
        {"date": "d", "close": 1.0}
    ]


def test_single_provider_passthrough():
    assert providers.eod_with_fallback(lambda **kw: [{"x": 1}], "SYM", providers=["yfinance"]) == [
        {"x": 1}
    ]


def test_all_empty_returns_empty_no_error():
    assert providers.eod_with_fallback(lambda **kw: [], "SYM", providers=["a", "b"]) == []


def test_all_fail_raises_last_error():
    def route(provider=None, **kw):
        raise ValueError(f"{provider} boom")

    with pytest.raises(ValueError):
        providers.eod_with_fallback(route, "SYM", providers=["a", "b"])


def test_passes_through_kwargs():
    seen = {}

    def route(symbol=None, provider=None, start_date=None, interval=None):
        seen.update(symbol=symbol, provider=provider, start_date=start_date, interval=interval)
        return [{"ok": 1}]

    providers.eod_with_fallback(
        route, "AAPL", start_date="2020-01-01", interval="1d", providers=["yfinance"]
    )
    assert seen == {
        "symbol": "AAPL",
        "provider": "yfinance",
        "start_date": "2020-01-01",
        "interval": "1d",
    }


def test_chain_parsing(monkeypatch):
    monkeypatch.setenv("EOD_PROVIDERS", "tiingo, yfinance ,")
    import config

    config.get_settings.cache_clear()
    try:
        assert config.get_settings().eod_provider_chain == ["tiingo", "yfinance"]
    finally:
        config.get_settings.cache_clear()
