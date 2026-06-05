"""Single explicit symbol map (SPEC.md §6 — symbol mapping is fragile).

CME contract  ↔  yfinance continuation symbol  ↔  spot/cash proxy.
Keep all symbol literals here, validated by the probe script — never scattered
through views.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    code: str           # our shorthand (e.g. "6E")
    name: str
    yf_symbol: str      # yfinance continuation symbol
    proxy_symbol: str   # spot/cash proxy to sanity-check the futures series
    proxy_name: str


WATCHLIST: dict[str, Instrument] = {
    "6E": Instrument("6E", "Euro FX futures", "6E=F", "EURUSD=X", "EUR/USD spot"),
    "6B": Instrument("6B", "British Pound futures", "6B=F", "GBPUSD=X", "GBP/USD spot"),
    "GC": Instrument("GC", "Gold futures", "GC=F", "XAUUSD=X", "Gold spot"),
    "NQ": Instrument("NQ", "E-mini Nasdaq-100", "NQ=F", "^NDX", "Nasdaq-100 cash"),
    "YM": Instrument("YM", "E-mini Dow", "YM=F", "^DJI", "Dow Jones cash"),
}
