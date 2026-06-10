"""Optional instrument metadata templates (SPEC.md §6 — symbol mapping is fragile).

These are **hints**, not limits — the terminal tracks whatever instruments the
user adds to the registry (SQLite). When adding a symbol that matches a template,
optional fields (COT code, TradingView symbol, news proxy, spot proxy) are
pre-filled. Validated by the probe script when present.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstrumentTemplate:
    code: str           # shorthand (e.g. "6E") when applicable
    name: str
    yf_symbol: str      # yfinance continuation symbol (futures)
    proxy_symbol: str   # spot/cash proxy to sanity-check the futures series
    proxy_name: str
    cot_code: str       # CFTC contract market code (futures COT)
    news_symbol: str    # liquid ETF proxy for free yfinance news
    tv_symbol: str      # TradingView continuous-futures symbol


# Reference templates for common CME futures — use when seeding metadata on add.
INSTRUMENT_TEMPLATES: dict[str, InstrumentTemplate] = {
    "6E": InstrumentTemplate("6E", "Euro FX futures", "6E=F", "EURUSD=X", "EUR/USD spot", "099741", "FXE", "CME:6E1!"),
    "6B": InstrumentTemplate("6B", "British Pound futures", "6B=F", "GBPUSD=X", "GBP/USD spot", "096742", "FXB", "CME:6B1!"),
    "GC": InstrumentTemplate("GC", "Gold futures", "GC=F", "GLD", "Gold (GLD ETF)", "088691", "GLD", "COMEX:GC1!"),
    "NQ": InstrumentTemplate("NQ", "E-mini Nasdaq-100", "NQ=F", "^NDX", "Nasdaq-100 cash", "209742", "QQQ", "CME_MINI:NQ1!"),
    "YM": InstrumentTemplate("YM", "E-mini Dow", "YM=F", "^DJI", "Dow Jones cash", "124603", "DIA", "CBOT_MINI:YM1!"),
}

# Back-compat alias for scripts that still import WATCHLIST.
WATCHLIST = INSTRUMENT_TEMPLATES


def template_for(asset: str, symbol: str) -> dict:
    """Return optional metadata dict for a new (asset, symbol) pair."""
    sym = symbol.strip().upper()
    asset = (asset or "").lower().strip()
    for t in INSTRUMENT_TEMPLATES.values():
        if asset == "futures" and sym in (t.code, t.yf_symbol.upper(), t.yf_symbol.upper().replace("=F", "")):
            return {
                "code": t.code,
                "name": t.name,
                "cot_code": t.cot_code,
                "news_symbol": t.news_symbol,
                "proxy_symbol": t.proxy_symbol,
                "proxy_name": t.proxy_name,
                "tv_symbol": t.tv_symbol,
            }
        if t.code == sym or t.yf_symbol.upper() == sym:
            return {
                "code": t.code,
                "name": t.name,
                "cot_code": t.cot_code,
                "news_symbol": t.news_symbol,
                "proxy_symbol": t.proxy_symbol,
                "proxy_name": t.proxy_name,
                "tv_symbol": t.tv_symbol,
            }
    # Sensible defaults per asset class.
    out: dict = {}
    if asset == "equity" or asset == "etf":
        out["news_symbol"] = symbol.strip().upper()
    if asset == "futures" and sym.endswith("=F"):
        root = sym.replace("=F", "")
        out["code"] = root
        out["tv_symbol"] = f"COMEX:{root}1!" if root in ("GC", "SI", "HG") else f"CME:{root}1!"
    return out
