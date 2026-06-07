"""OpenBB data functions for V2 — Watchlist (SPEC.md §4 V2).

Thin fetch→normalize→cache wrappers for the watchlist's daily OHLCV: the futures
series itself and its spot/cash proxy. All routes/params are Phase-0
probe-confirmed (yfinance daily OHLCV for futures, currency, and indices).

Proxy dispatch keeps the one explicit symbol map (obb_layer/symbols.py) as the
source of truth: '^...' → index router, '...=X' → currency router.
"""

from __future__ import annotations

from cache.store import cached
from circuit import guarded
from obb_layer.client import get_obb
from obb_layer.normalize import to_records


@cached("eod")
@guarded()
def futures_history(symbol: str, start_date: str | None = None) -> list[dict]:
    """Daily OHLCV for a futures continuation symbol (e.g. 'GC=F'). Provider: yfinance.

    `start_date` (YYYY-MM-DD) requests deeper history; omitted, yfinance returns
    its ~1-year default. The forecasting eval (§E) passes a multi-year start so
    Kronos gets its full 512-bar context.
    """
    obb = get_obb()
    kwargs: dict = {"symbol": symbol, "provider": "yfinance"}
    if start_date:
        kwargs["start_date"] = start_date
    return to_records(obb.derivatives.futures.historical(**kwargs))


@cached("eod")
@guarded()
def crypto_history(symbol: str, start_date: str | None = None) -> list[dict]:
    """Daily OHLCV for a crypto pair (e.g. 'BTC-USD'). Provider: yfinance.

    Used by the forecasting eval (§E) to test Kronos on crypto — the asset class
    it was actually trained/demoed on (BTC/USDT), unlike daily futures.
    """
    obb = get_obb()
    kwargs: dict = {"symbol": symbol, "provider": "yfinance"}
    if start_date:
        kwargs["start_date"] = start_date
    return to_records(obb.crypto.price.historical(**kwargs))


@cached("eod")
@guarded()
def fx_history(symbol: str, start_date: str | None = None) -> list[dict]:
    """Daily OHLCV for an FX pair (e.g. 'EURUSD'). Provider: yfinance."""
    obb = get_obb()
    kwargs: dict = {"symbol": symbol, "provider": "yfinance"}
    if start_date:
        kwargs["start_date"] = start_date
    return to_records(obb.currency.price.historical(**kwargs))


@cached("eod")
@guarded()
def proxy_history(proxy_symbol: str) -> list[dict]:
    """Daily OHLCV for a spot/cash proxy, routed by symbol shape.

    '^NDX'/'^DJI' → index router; 'EURUSD=X' → currency router (the '=X' is a
    yfinance suffix; the currency endpoint takes the bare pair); anything else
    (e.g. the 'GLD' gold ETF) → the ETF router. yfinance has no free gold-spot
    cross, so GC uses the GLD ETF as its proxy.
    """
    obb = get_obb()
    if proxy_symbol.startswith("^"):
        return to_records(obb.index.price.historical(symbol=proxy_symbol, provider="yfinance"))
    if proxy_symbol.endswith("=X"):
        pair = proxy_symbol[:-2]
        return to_records(obb.currency.price.historical(symbol=pair, provider="yfinance"))
    return to_records(obb.etf.historical(symbol=proxy_symbol, provider="yfinance"))
