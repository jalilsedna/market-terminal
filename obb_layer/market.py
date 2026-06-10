"""Market data functions for V2 — Watchlist (SPEC.md §4 V2).

Thin fetch→normalize→cache wrappers for daily OHLCV: futures, crypto, FX,
equities, ETFs, and spot/cash proxies. All price paths go through FMP (direct
REST for futures) or the configurable EOD provider chain (FMP first).
"""

from __future__ import annotations

from cache.store import cached
from circuit import guarded
from obb_layer import fmp_market
from obb_layer.client import get_obb
from obb_layer.providers import eod_with_fallback


@cached("eod")
@guarded()
def futures_history(
    symbol: str, start_date: str | None = None, interval: str = "1d"
) -> list[dict]:
    """OHLCV for a futures continuation symbol (e.g. 'GC=F'). Provider: FMP."""
    return fmp_market.history(symbol, start_date=start_date, interval=interval)


@cached("eod")
@guarded()
def crypto_history(
    symbol: str, start_date: str | None = None, interval: str = "1d"
) -> list[dict]:
    """OHLCV for a crypto pair (e.g. 'BTC-USD'). Tries the EOD provider chain
    with per-provider symbol mapping."""
    return eod_with_fallback(
        get_obb().crypto.price.historical, symbol, asset="crypto",
        start_date=start_date, interval=interval,
    )


@cached("eod")
@guarded()
def fx_history(
    symbol: str, start_date: str | None = None, interval: str = "1d"
) -> list[dict]:
    """OHLCV for an FX pair (e.g. 'EURUSD'). Tries the EOD provider chain."""
    return eod_with_fallback(
        get_obb().currency.price.historical, symbol, asset="forex",
        start_date=start_date, interval=interval,
    )


@cached("eod")
@guarded()
def equity_history(
    symbol: str, start_date: str | None = None, interval: str = "1d"
) -> list[dict]:
    """OHLCV for an equity/index ticker (e.g. 'AAPL'). Tries the EOD chain."""
    return eod_with_fallback(
        get_obb().equity.price.historical, symbol, start_date=start_date, interval=interval
    )


@cached("eod")
@guarded()
def etf_history(symbol: str, start_date: str | None = None, interval: str = "1d") -> list[dict]:
    """OHLCV for an ETF (e.g. 'SPY', 'GLD'). Tries the EOD provider chain."""
    return eod_with_fallback(
        get_obb().etf.historical, symbol, start_date=start_date, interval=interval
    )


@cached("eod")
@guarded()
def proxy_history(proxy_symbol: str) -> list[dict]:
    """Daily OHLCV for a spot/cash proxy, routed by symbol shape.

    '^NDX'/'^DJI' → index; 'EURUSD=X' → FX pair; 'GLD' etc. → ETF.
  """
    if proxy_symbol.startswith("^"):
        return eod_with_fallback(get_obb().index.price.historical, proxy_symbol)
    if proxy_symbol.endswith("=X"):
        return fx_history(proxy_symbol[:-2])
    return etf_history(proxy_symbol)
