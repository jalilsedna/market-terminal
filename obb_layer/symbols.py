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
    cot_code: str       # CFTC contract market code for COT (V4)
    news_symbol: str    # liquid ETF proxy that carries free yfinance news (V3)


# `cot_code` is the CFTC "contract market code". GC=088691 is probe-confirmed;
# the others are the standard legacy futures codes and should be verified via
# the /cot/search endpoint on first run (every COT response echoes
# `market_and_exchange_names`, so a wrong code is immediately visible).
#
# `news_symbol` is a liquid ETF that tracks the same underlying and carries free
# news via yfinance (the only free news provider in this OpenBB version): gold
# (GLD), Nasdaq-100 (QQQ), Dow (DIA), euro (FXE), pound (FXB).
WATCHLIST: dict[str, Instrument] = {
    "6E": Instrument("6E", "Euro FX futures", "6E=F", "EURUSD=X", "EUR/USD spot", "099741", "FXE"),
    "6B": Instrument("6B", "British Pound futures", "6B=F", "GBPUSD=X", "GBP/USD spot", "096742", "FXB"),
    "GC": Instrument("GC", "Gold futures", "GC=F", "XAUUSD=X", "Gold spot", "088691", "GLD"),
    "NQ": Instrument("NQ", "E-mini Nasdaq-100", "NQ=F", "^NDX", "Nasdaq-100 cash", "209742", "QQQ"),
    "YM": Instrument("YM", "E-mini Dow", "YM=F", "^DJI", "Dow Jones cash", "124603", "DIA"),
}
