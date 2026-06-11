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
    futures_symbol: str  # CME continuation symbol (e.g. GC=F)
    proxy_symbol: str   # spot/cash proxy to sanity-check the futures series
    proxy_name: str
    cot_code: str       # CFTC contract market code (futures COT)
    news_symbol: str    # liquid ETF proxy for FMP company news
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


# Curated CFTC "contract market codes" for common futures roots, so COT works for
# more than the five templated contracts. Best-effort from the CFTC COT report;
# the positioning view shows the resolved CFTC contract NAME, which is a built-in
# sanity check (a wrong code surfaces as the wrong market name). Roots not listed
# here fall back to `cot_search`. Verify with scripts/probe_providers.py.
CFTC_CODES: dict[str, str] = {
    # FX (CME)
    "6E": "099741", "6B": "096742", "6J": "097741", "6C": "090741",
    "6S": "092741", "6A": "232741", "6N": "112741", "6M": "095741",
    # Equity index
    "ES": "13874A", "NQ": "209742", "YM": "124603", "RTY": "239742",
    # Rates (CBOT)
    "ZB": "020601", "ZN": "043602", "ZF": "044601", "ZT": "042601", "UB": "020604",
    # Metals (COMEX/NYMEX)
    "GC": "088691", "SI": "084691", "HG": "085692", "PL": "076651", "PA": "075651",
    # Energy (NYMEX)
    "CL": "067651", "NG": "023651", "RB": "111659", "HO": "022651",
    # Grains / oilseeds (CBOT)
    "ZC": "002602", "ZS": "005602", "ZW": "001602", "KE": "001612",
    "ZL": "007601", "ZM": "026603",
    # Softs (ICE)
    "SB": "080732", "KC": "083731", "CC": "073732", "CT": "033661", "OJ": "040701",
    # Livestock (CME)
    "LE": "057642", "HE": "054642", "GF": "061641",
}


def cot_code_for(root: str | None) -> str | None:
    """CFTC contract code for a futures root ('GC', 'CL', 'ES'), or None if unmapped."""
    if not root:
        return None
    return CFTC_CODES.get(root.strip().upper().replace("=F", ""))


def template_for(asset: str, symbol: str) -> dict:
    """Return optional metadata dict for a new (asset, symbol) pair."""
    sym = symbol.strip().upper()
    asset = (asset or "").lower().strip()
    for t in INSTRUMENT_TEMPLATES.values():
        if asset == "futures" and sym in (t.code, t.futures_symbol.upper(), t.futures_symbol.upper().replace("=F", "")):
            return {
                "code": t.code,
                "name": t.name,
                "cot_code": t.cot_code,
                "news_symbol": t.news_symbol,
                "proxy_symbol": t.proxy_symbol,
                "proxy_name": t.proxy_name,
                "tv_symbol": t.tv_symbol,
            }
        if t.code == sym or t.futures_symbol.upper() == sym:
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
        code = cot_code_for(root)
        if code:
            out["cot_code"] = code
        out["tv_symbol"] = f"COMEX:{root}1!" if root in ("GC", "SI", "HG") else f"CME:{root}1!"
    return out
