"""FMP market history — futures and proxy OHLCV via FMP REST.

Maps canonical futures continuation symbols (``GC=F``) and spot proxies to FMP
tickers, then fetches EOD or intraday bars via ``obb_layer/fmp.py``.
"""

from __future__ import annotations

from typing import Any

from obb_layer import fmp

# CME continuation root → FMP symbol (commodity USD, FX pair, or cash index).
FUTURES_SYMBOL_MAP: dict[str, str] = {
    "GC=F": "GCUSD",
    "CL=F": "CLUSD",
    "NG=F": "NGUSD",
    "SI=F": "SIUSD",
    "HG=F": "HGUSD",
    "6E=F": "EURUSD",
    "6B=F": "GBPUSD",
    "NQ=F": "^NDX",
    "YM=F": "^DJI",
    "ES=F": "^GSPC",
    "RTY=F": "^RUT",
}

_INTERVAL_CHART: dict[str, str] = {
    "1m": "1min",
    "1min": "1min",
    "5m": "5min",
    "5min": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1hour",
    "1hour": "1hour",
    "4h": "4hour",
}


def resolve_fmp_symbol(symbol: str) -> str:
    """Canonical terminal symbol → FMP ticker."""
    s = symbol.upper().strip()
    if s in FUTURES_SYMBOL_MAP:
        return FUTURES_SYMBOL_MAP[s]
    if s.endswith("=F"):
        return f"{s[:-2]}USD"
    if s.endswith("=X"):
        return s[:-2]
    return s


def _as_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def _normalize_bars(rows: list[dict[str, Any]]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        raw_date = row.get("date")
        if raw_date is None:
            continue
        date_str = str(raw_date).replace(" ", "T").split("T")[0]
        if len(str(raw_date)) > 10 and " " in str(raw_date):
            date_str = str(raw_date)[:19]
        out.append({
            "date": date_str,
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": row.get("close"),
            "volume": row.get("volume"),
        })
    out.sort(key=lambda r: str(r["date"]))
    return out


def history(symbol: str, start_date: str | None = None, interval: str = "1d") -> list[dict]:
    """OHLCV history for a futures root, proxy, or portable ticker via FMP."""
    fmp_sym = resolve_fmp_symbol(symbol)
    if interval in ("1d", "1day", "daily", "d"):
        rows = _as_records(fmp.historical_eod_full(fmp_sym, from_=start_date))
        return _normalize_bars(rows)
    chart_interval = _INTERVAL_CHART.get(interval, interval)
    rows = _as_records(fmp.historical_chart(fmp_sym, chart_interval, from_=start_date))
    return _normalize_bars(rows)
