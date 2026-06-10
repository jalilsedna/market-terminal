"""FMP commodity forward curves — GC/CL/NG term structure (ROADMAP B3).

FMP has no dedicated futures-curve endpoint. We build a pseudo-curve from
``commodities-list`` (symbol + tradeMonth per contract) joined to live or EOD
prices via ``batch-commodity-quotes`` / ``historical-price-eod/full``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date as date_type
from typing import Any

from obb_layer import fmp

_MONTH = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

# Root -> filter on commodities-list rows (symbol + name).
_ROOT_FILTERS: dict[str, Callable[[dict[str, Any]], bool]] = {
    "GC": lambda e: (
        str(e.get("symbol", "")).upper().startswith("GC")
        and "gold" in str(e.get("name", "")).lower()
    ),
    "CL": lambda e: (
        str(e.get("symbol", "")).upper().startswith("CL")
        and any(k in str(e.get("name", "")).lower() for k in ("crude", "wti", "oil"))
    ),
    "NG": lambda e: (
        str(e.get("symbol", "")).upper().startswith("NG")
        and "natural gas" in str(e.get("name", "")).lower()
    ),
}


def _root(symbol: str) -> str:
    return (symbol or "").upper().replace("=F", "").strip()


def expiration_from_trade_month(trade_month: str, ref: date_type | None = None) -> str:
    """Map FMP tradeMonth (e.g. ``Jun``) to ``YYYY-MM`` for curve ordering."""
    ref = ref or date_type.today()
    key = (trade_month or "")[:3].title()
    month = _MONTH.get(key)
    if not month:
        raise ValueError(f"unknown trade month {trade_month!r}")
    year = ref.year
    if month < ref.month:
        year += 1
    return f"{year}-{month:02d}"


def _as_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def _quote_price(row: dict[str, Any]) -> float | None:
    for key in ("price", "close", "previousClose"):
        val = row.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return None


def _contracts_for_root(root: str) -> list[dict[str, Any]]:
    pred = _ROOT_FILTERS.get(root)
    if not pred:
        raise ValueError(f"unsupported FMP curve root {root!r}")
    return [e for e in _as_records(fmp.commodities_list()) if pred(e)]


def _live_prices() -> dict[str, float]:
    out: dict[str, float] = {}
    for row in _as_records(fmp.batch_commodity_quotes()):
        sym = row.get("symbol")
        price = _quote_price(row)
        if sym and price is not None:
            out[str(sym).upper()] = price
    return out


def _eod_close(symbol: str, as_of: str) -> float | None:
    rows = _as_records(fmp.commodity_eod_full(symbol, from_=as_of, to=as_of))
    if not rows:
        rows = _as_records(fmp.commodity_eod_full(symbol, from_=as_of, to=None))
    for row in rows:
        if str(row.get("date", ""))[:10] == as_of:
            return _quote_price(row)
    if rows:
        return _quote_price(rows[0])
    return None


def futures_curve(symbol: str, *, date: str | None = None, limit: int = 18) -> list[dict[str, Any]]:
    """Forward curve points: [{expiration, price}, ...] sorted by expiration."""
    root = _root(symbol)
    contracts = _contracts_for_root(root)
    if not contracts:
        raise fmp.FmpError(f"no FMP contracts listed for {root}")

    ref = date_type.fromisoformat(date) if date else date_type.today()
    meta: list[tuple[str, str]] = []
    for entry in contracts:
        sym = entry.get("symbol")
        trade_month = entry.get("tradeMonth")
        if not sym or not trade_month:
            continue
        try:
            exp = expiration_from_trade_month(str(trade_month), ref)
        except ValueError:
            continue
        meta.append((str(sym), exp))
    meta.sort(key=lambda x: x[1])
    meta = meta[: max(2, limit)]
    if len(meta) < 2:
        raise ValueError(f"curve has fewer than 2 listed expirations for {root}")

    live = None if date else _live_prices()
    points: list[dict[str, Any]] = []
    for sym, exp in meta:
        if date:
            price = _eod_close(sym, date)
        else:
            price = live.get(sym.upper()) if live else None
            if price is None:
                for row in _as_records(fmp.commodity_quote(sym)):
                    price = _quote_price(row)
                    if price is not None:
                        break
        if price is None:
            continue
        points.append({"expiration": exp, "price": round(float(price), 4)})
    points.sort(key=lambda p: p["expiration"])
    if len(points) < 2:
        raise ValueError(f"curve has fewer than 2 priced expirations for {root}")
    return points
