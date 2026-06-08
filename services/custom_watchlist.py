"""Custom multi-asset watchlist — live data layer (ROADMAP C6).

The pure add/remove/list store is `services/custom_store.py` (CI-tested). This
adds the live price + change + volatility/regime read per instrument, across
asset classes (futures, crypto, forex, equity, ETF). Services call `obb_layer/`,
never OpenBB directly; each row is fault-tolerant.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from obb_layer.market import (
    crypto_history,
    equity_history,
    etf_history,
    futures_history,
    fx_history,
)
from services.custom_store import list_items
from vol import realized_vol_series, vol_regime

DISCLAIMER = "EOD prices + realized-vol read — research context, not a trade trigger."

# asset class -> obb_layer fetcher. crypto: 'BTC-USD'; forex: 'EURUSD';
# futures: 'GC=F'; equity: 'AAPL'; etf: 'SPY'.
FETCHERS = {
    "futures": futures_history,
    "crypto": crypto_history,
    "forex": fx_history,
    "equity": equity_history,
    "etf": etf_history,
}
_VOL_WINDOW = 21
_MIN_VOL_BARS = _VOL_WINDOW + 40


def _metrics(asset: str, symbol: str) -> dict:
    """Live last price, % changes, and a vol/regime read for one instrument."""
    fetch = FETCHERS.get(asset)
    if fetch is None:
        return {"ok": False, "error": f"unknown asset {asset!r}"}
    records = fetch(symbol, start_date=(date.today() - timedelta(days=400)).isoformat())
    if not records:
        return {"ok": False, "error": "no data (bad symbol / provider throttled?)"}
    recs = sorted(records, key=lambda r: str(r.get("date", "")))
    closes = np.array([float(r["close"]) for r in recs if r.get("close") is not None])
    if len(closes) < 2:
        return {"ok": False, "error": "insufficient data"}

    def chg(n: int):
        return None if len(closes) <= n else round((closes[-1] / closes[-1 - n] - 1) * 100, 2)

    out = {
        "ok": True,
        "last": round(float(closes[-1]), 4),
        "change_1d_pct": chg(1),
        "change_1w_pct": chg(5),
        "change_1m_pct": chg(21),
        "as_of": recs[-1].get("date"),
    }
    if len(closes) >= _MIN_VOL_BARS:
        try:
            rv = realized_vol_series(closes, window=_VOL_WINDOW)
            cur = float(rv[-1])
            out["vol_annualized"] = round(cur, 4)
            out["regime"] = vol_regime(cur, rv[:-1])["regime"]
        except Exception:  # noqa: BLE001 — vol is a bonus; price still shows
            pass
    return out


def dashboard() -> dict:
    """All custom instruments with live price + vol/regime."""
    out = []
    for it in list_items():
        try:
            metrics = _metrics(it["asset"], it["symbol"])
        except Exception as exc:  # noqa: BLE001 — one symbol must not sink the list
            metrics = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:160]}
        out.append({**it, **metrics})
    return {"instruments": out, "count": len(out), "disclaimer": DISCLAIMER}
