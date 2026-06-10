"""Symbol autocomplete — filter suggestions as the user types.

Equity/ETF → Alpaca catalog when configured, plus a curated fallback list.
Forex, crypto, futures → built-in catalogs (+ instrument templates).
"""

from __future__ import annotations

from config import get_settings
from obb_layer.symbols import INSTRUMENT_TEMPLATES

# Canonical symbols the terminal's fetchers expect.
_FOREX_MAJORS = (
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
    "EURJPY", "GBPJPY", "EURGBP", "AUDJPY", "EURAUD", "EURCHF", "CADJPY",
    "CHFJPY", "NZDJPY", "GBPAUD", "GBPCAD", "AUDCAD", "AUDNZD",
)
_CRYPTO_MAJORS = (
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "DOGE-USD",
    "AVAX-USD", "DOT-USD", "LINK-USD", "MATIC-USD", "LTC-USD", "BCH-USD",
    "UNI-USD", "ATOM-USD", "NEAR-USD", "APT-USD", "ARB-USD", "OP-USD",
)
_FUTURES_EXTRA = (
    "ES=F", "NQ=F", "YM=F", "RTY=F", "6E=F", "6B=F", "6J=F", "6A=F",
    "GC=F", "SI=F", "HG=F", "CL=F", "NG=F", "ZB=F", "ZN=F", "ZC=F", "ZS=F",
)
_EQUITY_MAJORS = (
    ("AAPL", "Apple"), ("MSFT", "Microsoft"), ("GOOGL", "Alphabet A"), ("GOOG", "Alphabet C"),
    ("AMZN", "Amazon"), ("NVDA", "NVIDIA"), ("META", "Meta"), ("TSLA", "Tesla"),
    ("BRK.B", "Berkshire Hathaway"), ("JPM", "JPMorgan"), ("V", "Visa"), ("MA", "Mastercard"),
    ("UNH", "UnitedHealth"), ("XOM", "Exxon Mobil"), ("JNJ", "Johnson & Johnson"),
    ("WMT", "Walmart"), ("PG", "Procter & Gamble"), ("HD", "Home Depot"), ("BAC", "Bank of America"),
    ("CVX", "Chevron"), ("KO", "Coca-Cola"), ("PEP", "PepsiCo"), ("COST", "Costco"),
    ("AMD", "AMD"), ("NFLX", "Netflix"), ("CRM", "Salesforce"), ("ORCL", "Oracle"),
    ("IBM", "IBM"), ("INTC", "Intel"), ("QCOM", "Qualcomm"), ("AVGO", "Broadcom"),
)
_ETF_MAJORS = (
    ("SPY", "SPDR S&P 500"), ("QQQ", "Invesco QQQ"), ("IWM", "Russell 2000"), ("DIA", "Dow Jones"),
    ("GLD", "Gold"), ("SLV", "Silver"), ("TLT", "20+ Year Treasury"), ("HYG", "High Yield Corp"),
    ("XLF", "Financials"), ("XLE", "Energy"), ("XLV", "Health Care"), ("XLK", "Technology"),
    ("VOO", "Vanguard S&P 500"), ("VTI", "Total Stock Market"), ("VEA", "Developed Markets"),
    ("VWO", "Emerging Markets"), ("AGG", "US Aggregate Bond"), ("EEM", "Emerging Markets"),
    ("EFA", "EAFE"), ("ARKK", "ARK Innovation"), ("SMH", "Semiconductors"), ("IBIT", "Bitcoin ETF"),
)


def _match(query: str, symbol: str, name: str = "") -> bool:
    q = query.strip().upper()
    if not q:
        return True
    blob = f"{symbol} {name}".upper()
    return q in blob or blob.startswith(q)


def _hit(symbol: str, name: str, asset: str) -> dict:
    return {"symbol": symbol, "name": name, "asset": asset, "label": f"{symbol} · {name}"}


def _curated_equity_etf(asset: str, query: str, *, limit: int, seen: set[str]) -> list[dict]:
    rows = _ETF_MAJORS if asset == "etf" else _EQUITY_MAJORS
    out: list[dict] = []
    for sym, name in rows:
        key = sym.upper()
        if key in seen:
            continue
        if not _match(query, sym, name):
            continue
        seen.add(key)
        out.append(_hit(sym, name, asset))
        if len(out) >= limit:
            break
    return out


def _alpaca_hits(asset: str, query: str, *, limit: int) -> list[dict]:
    from obb_layer import alpaca

    raw = alpaca.list_assets(search=query or None, limit=limit)
    out: list[dict] = []
    for r in raw:
        ta = r.get("terminal_asset") or "equity"
        if asset == "etf" and ta != "etf":
            continue
        if asset == "equity" and ta == "etf":
            continue
        out.append(_hit(r["symbol"], r.get("name") or r["symbol"], ta))
    return out


def search(asset: str, query: str = "", *, limit: int = 25) -> list[dict]:
    """Return autocomplete suggestions for one asset class."""
    asset = (asset or "").lower().strip()
    q = (query or "").strip()
    limit = max(1, min(limit, 100))
    out: list[dict] = []
    seen: set[str] = set()

    if asset in ("equity", "etf"):
        if get_settings().alpaca_enabled:
            try:
                for h in _alpaca_hits(asset, q, limit=limit):
                    key = h["symbol"].upper()
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(h)
            except Exception:  # noqa: BLE001 — fall through to curated list
                pass
        curated = _curated_equity_etf(asset, q, limit=limit - len(out), seen=seen)
        out.extend(curated)
        return out[:limit]

    if asset == "forex":
        for sym in _FOREX_MAJORS:
            if _match(q, sym):
                out.append(_hit(sym, sym, "forex"))
            if len(out) >= limit:
                break
        return out

    if asset == "crypto":
        for sym in _CRYPTO_MAJORS:
            if _match(q, sym.replace("-", ""), sym):
                out.append(_hit(sym, sym.split("-")[0], "crypto"))
            if len(out) >= limit:
                break
        return out

    if asset == "futures":
        seen_sym: set[str] = set()
        for t in INSTRUMENT_TEMPLATES.values():
            if _match(q, t.futures_symbol, t.name) or _match(q, t.code, t.name):
                sym = t.futures_symbol
                if sym not in seen_sym:
                    out.append(_hit(sym, t.name, "futures"))
                    seen_sym.add(sym)
        for sym in _FUTURES_EXTRA:
            if sym in seen_sym:
                continue
            root = sym.replace("=F", "")
            if _match(q, sym, root):
                out.append(_hit(sym, root + " futures", "futures"))
                seen_sym.add(sym)
            if len(out) >= limit:
                break
        return out[:limit]

    return []
