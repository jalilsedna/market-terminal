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
from obb_layer.providers import eod_with_fallback


@cached("eod")
@guarded()
def futures_history(
    symbol: str, start_date: str | None = None, interval: str = "1d"
) -> list[dict]:
    """OHLCV for a futures continuation symbol (e.g. 'GC=F'). Provider: yfinance.

    `start_date` (YYYY-MM-DD) requests deeper history; omitted, yfinance returns
    its ~1-year default. `interval` ('1d', '1h', …) sets the bar frequency — the
    forecasting eval (§E) uses '1h' to test Kronos at its native intraday cadence
    (yfinance caps intraday history to ~730 days).
    """
    obb = get_obb()
    kwargs: dict = {"symbol": symbol, "provider": "yfinance", "interval": interval}
    if start_date:
        kwargs["start_date"] = start_date
    return to_records(obb.derivatives.futures.historical(**kwargs))


@cached("eod")
@guarded()
def crypto_history(
    symbol: str, start_date: str | None = None, interval: str = "1d"
) -> list[dict]:
    """OHLCV for a crypto pair (e.g. 'BTC-USD'). Tries the EOD provider chain
    (B-next) with per-provider symbol mapping (`BTC-USD` → Polygon `X:BTCUSD`,
    Tiingo `btcusd`, …), falling back to yfinance. `interval` ('1d', '1h', …)
    sets the bar frequency; the forecasting eval (§E) uses '1h'.
    """
    return eod_with_fallback(
        get_obb().crypto.price.historical, symbol, asset="crypto",
        start_date=start_date, interval=interval,
    )


@cached("eod")
@guarded()
def fx_history(
    symbol: str, start_date: str | None = None, interval: str = "1d"
) -> list[dict]:
    """OHLCV for an FX pair (e.g. 'EURUSD'). Tries the EOD provider chain (B-next)
    with per-provider symbol mapping (`EURUSD` → Polygon `C:EURUSD`, …), falling
    back to yfinance. `interval` ('1d', '1h', …) sets the bar frequency."""
    return eod_with_fallback(
        get_obb().currency.price.historical, symbol, asset="forex",
        start_date=start_date, interval=interval,
    )


@cached("eod")
@guarded()
def equity_history(
    symbol: str, start_date: str | None = None, interval: str = "1d"
) -> list[dict]:
    """OHLCV for an equity/index ticker (e.g. 'AAPL'). Tries the EOD provider
    chain (B4) — symbols are portable across providers here. Used by C6."""
    return eod_with_fallback(
        get_obb().equity.price.historical, symbol, start_date=start_date, interval=interval
    )


@cached("eod")
@guarded()
def etf_history(symbol: str, start_date: str | None = None, interval: str = "1d") -> list[dict]:
    """OHLCV for an ETF (e.g. 'SPY', 'GLD'). Tries the EOD provider chain (B4).
    Used by the custom multi-asset watchlist (C6)."""
    return eod_with_fallback(
        get_obb().etf.historical, symbol, start_date=start_date, interval=interval
    )


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
