"""Symbol autocomplete — filter suggestions as the user types.

Equity/ETF → Alpaca catalog (read-only). Forex, crypto, futures → curated
canonical lists (+ instrument templates). No network for non-equity classes.
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


def _match(query: str, symbol: str, name: str = "") -> bool:
    q = query.strip().upper()
    if not q:
        return True
    blob = f"{symbol} {name}".upper()
    return q in blob or blob.startswith(q)


def _hit(symbol: str, name: str, asset: str) -> dict:
    return {"symbol": symbol, "name": name, "asset": asset, "label": f"{symbol} · {name}"}


def search(asset: str, query: str = "", *, limit: int = 25) -> list[dict]:
    """Return autocomplete suggestions for one asset class."""
    asset = (asset or "").lower().strip()
    q = (query or "").strip()
    limit = max(1, min(limit, 100))
    out: list[dict] = []

    if asset in ("equity", "etf"):
        if not get_settings().alpaca_enabled:
            return []
        from obb_layer import alpaca

        try:
            klass = "crypto" if asset == "crypto" else None
            raw = alpaca.list_assets(search=q or None, asset_class=klass, limit=limit)
            for r in raw:
                ta = r.get("terminal_asset") or asset
                if asset == "etf" and ta != "etf":
                    continue
                if asset == "equity" and ta not in ("equity", "etf"):
                    continue
                out.append(_hit(r["symbol"], r.get("name") or r["symbol"], ta))
        except Exception:  # noqa: BLE001
            return []
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
        seen: set[str] = set()
        for t in INSTRUMENT_TEMPLATES.values():
            if _match(q, t.yf_symbol, t.name) or _match(q, t.code, t.name):
                sym = t.yf_symbol
                if sym not in seen:
                    out.append(_hit(sym, t.name, "futures"))
                    seen.add(sym)
        for sym in _FUTURES_EXTRA:
            if sym in seen:
                continue
            root = sym.replace("=F", "")
            if _match(q, sym, root):
                out.append(_hit(sym, root + " futures", "futures"))
                seen.add(sym)
            if len(out) >= limit:
                break
        return out[:limit]

    return []
