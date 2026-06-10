"""Unified instruments dashboard — all tracked assets (futures, crypto, forex, equity, ETF).

Per instrument: EOD price, 1d/1w/1m % change, ATR(14) where OHLCV allows,
optional spot proxy (futures), and vol/regime read. The registry starts empty;
users add symbols via /instruments.

Services never import OpenBB directly — they call `obb_layer/`.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np

from concurrency import parallel_map
from obb_layer import market
from services import instruments as reg
from services.custom_watchlist import FETCHERS, _metrics
from vol import realized_vol_series, vol_regime

DISCLAIMER = "EOD prices — research context, not a trade signal."
_VOL_WINDOW = 21
_MIN_VOL_BARS = _VOL_WINDOW + 40


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
    atr = sum(true_ranges[:length]) / length
    for tr in true_ranges[length:]:
        atr = (atr * (length - 1) + tr) / length
    return round(atr, 5)


def _vol_read(closes: np.ndarray) -> dict:
    if len(closes) < _MIN_VOL_BARS:
        return {}
    try:
        rv = realized_vol_series(closes, window=_VOL_WINDOW)
        cur = float(rv[-1])
        return {"vol_annualized": round(cur, 4), "regime": vol_regime(cur, rv[:-1])["regime"]}
    except Exception:  # noqa: BLE001
        return {}


def instrument_summary(ref: str) -> dict:
    """Full row for one tracked instrument."""
    inst = reg.resolve(ref)
    base = {
        "id": inst.id,
        "code": inst.code,
        "asset": inst.asset,
        "symbol": inst.symbol,
        "name": inst.label,
        "capabilities": inst.capabilities(),
    }

    if inst.asset == "futures":
        fetch = FETCHERS["futures"]
        fut_records = fetch(inst.symbol, start_date=(date.today() - timedelta(days=400)).isoformat())
        fut = _ohlcv_snapshot(fut_records)
        atr = _atr(fut_records, 14)
        close = fut.get("close")
        atr_pct = round(atr / close * 100, 3) if (atr is not None and close) else None
        proxy_sym = inst.meta.get("proxy_symbol")
        proxy = None
        if proxy_sym:
            try:
                proxy = {
                    "symbol": proxy_sym,
                    "name": inst.meta.get("proxy_name") or proxy_sym,
                    **_ohlcv_snapshot(market.proxy_history(proxy_sym)),
                }
            except Exception as exc:  # noqa: BLE001
                proxy = {"symbol": proxy_sym, "ok": False, "error": type(exc).__name__}
        closes = np.array([float(r["close"]) for r in fut_records if r.get("close") is not None])
        return {
            **base,
            "ok": True,
            "future": fut,
            "atr_14": atr,
            "atr_14_pct": atr_pct,
            "proxy": proxy,
            **_vol_read(closes),
        }

    metrics = _metrics(inst.asset, inst.symbol)
    return {**base, **metrics}


def _one(inst: reg.TrackedInstrument) -> tuple[str, dict]:
    try:
        row = instrument_summary(inst.id)
        return inst.id, {"ok": True, **row} if row.get("ok") is not False else row
    except Exception as exc:  # noqa: BLE001
        return inst.id, {
            "ok": False,
            "id": inst.id,
            "name": inst.label,
            "asset": inst.asset,
            "symbol": inst.symbol,
            "error": f"{type(exc).__name__}: {exc}"[:200],
        }


def watchlist() -> dict:
    """All tracked instruments with live metrics (empty registry → empty dict)."""
    items = reg.list_all()
    if not items:
        return {"instruments": {}, "count": 0, "disclaimer": DISCLAIMER}
    rows = dict(parallel_map(_one, items))
    return {"instruments": rows, "count": len(rows), "disclaimer": DISCLAIMER}
