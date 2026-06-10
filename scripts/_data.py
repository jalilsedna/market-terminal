"""Shared OHLCV loading for the eval scripts — futures/crypto/forex via obb_layer.

Keeps the data-fetch + asset-resolution in one place so the Kronos and volatility
evals agree on symbols, history depth, and intraday caps.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from obb_layer.market import crypto_history, futures_history, fx_history
from obb_layer.symbols import WATCHLIST

OHLCV = ("open", "high", "low", "close", "volume")


def resolve(asset: str, instrument: str):
    """(asset class, instrument) → (provider symbol, fetcher)."""
    if asset == "futures":
        if instrument in WATCHLIST:
            return WATCHLIST[instrument].futures_symbol, futures_history
        return instrument, futures_history  # raw yf symbol (e.g. 'CL=F')
    if asset == "crypto":
        return instrument, crypto_history  # e.g. 'BTC-USD'
    if asset == "forex":
        return instrument, fx_history  # e.g. 'EURUSD'
    raise SystemExit(f"unknown asset class {asset!r}; choose futures | crypto | forex")


def load_ohlcv(asset: str, instrument: str, years: int, interval: str = "1d") -> pd.DataFrame:
    """Tidy OHLCV DataFrame (date + OHLCV columns), sorted ascending."""
    symbol, fetch = resolve(asset, instrument)
    days = 365 * years + 10
    if interval != "1d":
        days = min(days, 729)  # provider caps intraday history (~730d for 1h)
    start = (date.today() - timedelta(days=days)).isoformat()
    records = fetch(symbol, start_date=start, interval=interval)
    if not records:
        raise SystemExit(f"no OHLCV for {symbol} (provider down / throttled / bad symbol?)")
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    missing = [c for c in OHLCV if c not in df.columns]
    if missing:
        raise SystemExit(f"OHLCV columns missing: {missing}")
    return df[["date", *OHLCV]]
