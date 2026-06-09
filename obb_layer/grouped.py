"""Polygon/Massive Grouped Daily — whole-market OHLCV in one REST call.

The **free** REST tier's grouped-daily aggregates endpoint returns *every* US
stock's daily bar for a date in a single call — the basis for the Movers screener
(`services/movers.py`) without the paid Flat Files / S3 product. It uses the same
`POLYGON_API_KEY` as the rest of the polygon integration; OpenBB's polygon
provider doesn't expose this market-wide route, so it lives here (the sanctioned
"OpenBB lacks it → extend in obb_layer" path, CLAUDE.md).

`httpx` is imported lazily inside the fetch so the pure parser (`parse_grouped`)
— and anything importing this module — works without it (keeps CI light).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from config import get_settings

_BASE = "https://api.polygon.io"  # legacy endpoint still served by Massive
_GROUPED = "/v2/aggs/grouped/locale/us/market/stocks/{day}"


def parse_grouped(results: list[dict] | None) -> dict[str, dict]:
    """Grouped-daily `results` rows → {ticker: {open,high,low,close,volume,
    transactions}}. Polygon keys: T=ticker, o/h/l/c, v=volume, n=transactions.
    Bad rows are skipped. Pure — unit-tested in CI."""
    out: dict[str, dict] = {}
    for r in results or []:
        ticker = (r.get("T") or "").strip()
        if not ticker:
            continue
        try:
            out[ticker] = {
                "open": float(r["o"]),
                "high": float(r["h"]),
                "low": float(r["l"]),
                "close": float(r["c"]),
                "volume": float(r.get("v") or 0.0),
                "transactions": int(r.get("n") or 0),
            }
        except (KeyError, ValueError, TypeError):
            continue
    return out


def fetch_grouped_daily(day: str) -> dict[str, dict]:
    """Fetch one date's whole-market bars ({ticker: row}); empty on a non-trading
    day. `day` is YYYY-MM-DD. Raises a sanitized RuntimeError on HTTP errors — the
    raw httpx error embeds the apiKey query param, so we never propagate it."""
    import httpx  # noqa: PLC0415 — lazy: only needed at fetch time

    key = get_settings().polygon_api_key
    url = _BASE + _GROUPED.format(day=day)
    try:
        resp = httpx.get(url, params={"adjusted": "true", "apiKey": key}, timeout=30.0)
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # Never leak the key (it's in the request URL's query). Surface status only.
        raise RuntimeError(f"grouped-daily {day}: HTTP {exc.response.status_code}") from None
    except httpx.HTTPError as exc:
        raise RuntimeError(f"grouped-daily {day}: {type(exc).__name__}") from None
    return parse_grouped(resp.json().get("results"))


def recent_trading_days(count: int = 2, lookback: int = 8) -> list[tuple[str, dict]]:
    """The `count` most recent trading days with data, newest-first, as
    (day, {ticker: row}). Walks back from today, skipping weekends (no call) and
    any day that returns no data — including **today**, which the free tier 403s
    until the session settles, and holidays. Only raises if *every* attempt failed
    (e.g. a bad key), so a forbidden recent day degrades to the prior session."""
    found: list[tuple[str, dict]] = []
    last_error: Exception | None = None
    d = datetime.now(UTC).date()
    for _ in range(lookback):
        if d.weekday() < 5:  # Mon–Fri only; skip weekends without a call
            try:
                rows = fetch_grouped_daily(d.isoformat())
            except RuntimeError as exc:  # forbidden/unavailable day → skip, walk back
                last_error, rows = exc, {}
            if rows:
                found.append((d.isoformat(), rows))
                if len(found) >= count:
                    break
        d -= timedelta(days=1)
    if not found and last_error is not None:
        raise last_error  # nothing worked at all → surface the (sanitized) cause
    return found

