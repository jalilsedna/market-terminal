"""Market-wide Movers screener (ROADMAP — Flat Files).

Top gainers / losers / most-active across the **entire** US stock market, from
Massive Flat Files (one ~300 KB daily file = every ticker's OHLCV). The compute
is pure (`compute_movers`) and unit-tested; `movers()` wires in the S3 fetch and
caches the result for the day (EOD TTL). Research context, never a trade trigger.

We filter to liquid, plain-symbol common stocks/ETFs (price ≥ $1, a dollar-volume
floor, `^[A-Z]{1,5}$` tickers) so the lists are signal, not penny-stock /
warrant / unit noise.
"""

from __future__ import annotations

import re

from cache.store import cached
from obb_layer import flatfiles

_PLAIN_TICKER = re.compile(r"^[A-Z]{1,5}$")

DISCLAIMER = "Whole-market EOD scan from Massive Flat Files (T+1) — research context, not a trade trigger."


def compute_movers(
    today: dict[str, dict],
    prev: dict[str, dict],
    *,
    min_price: float = 1.0,
    min_dollar_volume: float = 5_000_000.0,
    top_n: int = 20,
) -> dict:
    """Rank movers from two day-aggregate snapshots ({ticker: {close,volume,…}}).

    Returns gainers/losers (by 1d % change) and most-active (by dollar volume),
    each capped at `top_n`, plus the universe size after filtering. Pure.
    """
    rows: list[dict] = []
    for ticker, t in today.items():
        if not _PLAIN_TICKER.match(ticker):
            continue
        p = prev.get(ticker)
        if not p:
            continue
        close, prev_close = t.get("close"), p.get("close")
        volume = t.get("volume") or 0.0
        if not close or not prev_close or close < min_price:
            continue
        dollar_volume = close * volume
        if dollar_volume < min_dollar_volume:
            continue
        rows.append({
            "ticker": ticker,
            "close": round(close, 4),
            "change_1d_pct": round((close / prev_close - 1.0) * 100.0, 2),
            "volume": volume,
            "dollar_volume": dollar_volume,
        })

    by_change = sorted(rows, key=lambda r: r["change_1d_pct"])
    by_dollar = sorted(rows, key=lambda r: r["dollar_volume"], reverse=True)
    return {
        "universe": len(rows),
        "filters": {"min_price": min_price, "min_dollar_volume": min_dollar_volume},
        "gainers": list(reversed(by_change[-top_n:])),
        "losers": by_change[:top_n],
        "most_active": by_dollar[:top_n],
        "disclaimer": DISCLAIMER,
    }


@cached("eod")
def movers(top_n: int = 20, min_price: float = 1.0, min_dollar_volume: float = 5_000_000.0) -> dict:
    """Whole-market movers from the two most recent daily Flat Files (today vs
    prior day). Cached for the day. Raises if Flat Files aren't reachable."""
    keys = flatfiles.latest_day_agg_keys(2)
    if len(keys) < 2:
        raise RuntimeError("need at least 2 daily Flat Files to compute movers")
    prev = flatfiles.fetch_day_aggs(keys[-2])
    today = flatfiles.fetch_day_aggs(keys[-1])
    result = compute_movers(
        today, prev, min_price=min_price, min_dollar_volume=min_dollar_volume, top_n=top_n
    )
    result["as_of"] = flatfiles.date_from_key(keys[-1])
    result["prev"] = flatfiles.date_from_key(keys[-2])
    return result
