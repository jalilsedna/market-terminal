"""V2 — Watchlist domain logic (SPEC.md §4 V2).

For each contract in the fixed watchlist (obb_layer/symbols.py): last EOD OHLCV,
day/week/month % change, and ATR(14) — shown beside its spot/cash proxy so the
futures series can be sanity-checked against the underlying.

ATR(14) is computed inline with Wilder's method: it's a small standard formula
on OHLCV we already hold, not a data source, so there's no need to round-trip
our own series back through OpenBB's `technical` extension.

Services never import OpenBB directly — they call `obb_layer/`.
"""

from __future__ import annotations

from typing import Any

from concurrency import parallel_map
from obb_layer import market
from obb_layer.symbols import WATCHLIST


def _num(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _pct(latest: float | None, prior: float | None) -> float | None:
    if latest is None or prior in (None, 0):
        return None
    return round((latest - prior) / prior * 100, 2)


def _nth_back(values: list[float], n: int) -> float | None:
    return values[-1 - n] if len(values) > n else None


def _ohlcv_snapshot(records: list[dict]) -> dict:
    """Latest close + 1d/1w/1m % change from ordered (oldest→newest) OHLCV rows."""
    closes = [c for r in records if (c := _num(r.get("close"))) is not None]
    if not closes:
        raise ValueError("no close prices")
    latest = records[-1]
    last_close = closes[-1]
    return {
        "as_of": str(latest.get("date"))[:10],
        "open": _num(latest.get("open")),
        "high": _num(latest.get("high")),
        "low": _num(latest.get("low")),
        "close": round(last_close, 5),
        "volume": _num(latest.get("volume")),
        "change_1d_pct": _pct(last_close, _nth_back(closes, 1)),
        "change_1w_pct": _pct(last_close, _nth_back(closes, 5)),
        "change_1m_pct": _pct(last_close, _nth_back(closes, 21)),
    }


def _atr(records: list[dict], length: int = 14) -> float | None:
    """ATR(length) via Wilder's smoothing over OHLCV rows (oldest→newest)."""
    rows = [
        r for r in records
        if _num(r.get("high")) is not None
        and _num(r.get("low")) is not None
        and _num(r.get("close")) is not None
    ]
    if len(rows) < length + 1:
        return None
    true_ranges: list[float] = []
    for i in range(1, len(rows)):
        high, low = _num(rows[i]["high"]), _num(rows[i]["low"])
        prev_close = _num(rows[i - 1]["close"])
        true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    # Seed with the simple average of the first `length` TRs, then Wilder-smooth.
    atr = sum(true_ranges[:length]) / length
    for tr in true_ranges[length:]:
        atr = (atr * (length - 1) + tr) / length
    return round(atr, 5)


def instrument_summary(code: str) -> dict:
    """Full V2 row for one watchlist instrument (future + ATR + proxy)."""
    key = code.upper()
    if key not in WATCHLIST:
        raise ValueError(f"unknown instrument '{code}'; known: {', '.join(WATCHLIST)}")
    inst = WATCHLIST[key]

    fut_records = market.futures_history(inst.yf_symbol)
    fut = _ohlcv_snapshot(fut_records)
    atr = _atr(fut_records, 14)

    # Proxy is best-effort: a failed proxy must not sink the future's data.
    try:
        proxy = {"symbol": inst.proxy_symbol, "name": inst.proxy_name,
                 **_ohlcv_snapshot(market.proxy_history(inst.proxy_symbol))}
    except Exception as exc:  # noqa: BLE001
        proxy = {"symbol": inst.proxy_symbol, "name": inst.proxy_name,
                 "ok": False, "error": f"{type(exc).__name__}"}

    # ATR as a % of price = atr / close * 100 (a ratio, not a period-over-period
    # change). A typical daily reading is low single digits.
    close = fut.get("close")
    atr_pct = round(atr / close * 100, 3) if (atr is not None and close) else None

    return {
        "code": inst.code,
        "name": inst.name,
        "future_symbol": inst.yf_symbol,
        "future": fut,
        "atr_14": atr,
        "atr_14_pct": atr_pct,
        "proxy": proxy,
    }


def _one(item) -> tuple[str, dict]:
    key, inst = item
    try:
        return key, {"ok": True, **instrument_summary(key)}
    except Exception as exc:  # noqa: BLE001 — one instrument must not sink the view
        return key, {"ok": False, "code": inst.code, "name": inst.name,
                     "error": f"{type(exc).__name__}: {exc}"[:200]}


def watchlist() -> dict:
    """V2 across the whole watchlist; each instrument fetched concurrently."""
    return dict(parallel_map(_one, WATCHLIST.items()))
