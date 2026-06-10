"""V6 — Screener / Sector Rotation domain logic (SPEC.md §4 V6).

Two pieces:
- Sector rotation/breadth: 1d/1w/1m % change for the 11 SPDR sector ETFs,
  ranked — the rotation read behind the index futures (a free stand-in for the
  spec's compare.groups heatmap, which this OpenBB version doesn't expose).
- A pass-through equity screener (FMP) with normalized rows.

Services never import OpenBB directly — they call `obb_layer/`.
"""

from __future__ import annotations

from typing import Any

from concurrency import parallel_map
from obb_layer import screener

# The 11 S&P sector SPDR ETFs → sector label (SPEC §4 V6 sector rotation).
SECTOR_ETFS: dict[str, str] = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Health Care",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLC": "Communication Services",
}


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


def _changes(records: list[dict]) -> dict:
    closes = [c for r in records if (c := _num(r.get("close"))) is not None]
    if not closes:
        raise ValueError("no close prices")
    last = closes[-1]
    return {
        "as_of": str(records[-1].get("date"))[:10],
        "close": round(last, 4),
        "change_1d_pct": _pct(last, _nth_back(closes, 1)),
        "change_1w_pct": _pct(last, _nth_back(closes, 5)),
        "change_1m_pct": _pct(last, _nth_back(closes, 21)),
    }


def _sector_one(item: tuple[str, str]) -> dict:
    etf, sector = item
    try:
        return {"etf": etf, "sector": sector, **_changes(screener.etf_history(etf))}
    except Exception as exc:  # noqa: BLE001 — one ETF must not sink the view
        return {"etf": etf, "sector": sector, "_error": type(exc).__name__}


def sector_rotation() -> dict:
    """1d/1w/1m % change for the 11 sector ETFs, ranked by 1-week performance.

    The 11 ETF fetches run concurrently — they're independent and network-bound.
    """
    fetched = parallel_map(_sector_one, SECTOR_ETFS.items())
    rows = [r for r in fetched if "_error" not in r]
    errors = {r["etf"]: r["_error"] for r in fetched if "_error" in r}

    if not rows and errors:
        raise RuntimeError(f"all sector fetches failed (e.g. {next(iter(errors.values()))})")

    rows.sort(key=lambda r: (r.get("change_1w_pct") is not None, r.get("change_1w_pct") or 0),
              reverse=True)
    return {
        "as_of": rows[0]["as_of"] if rows else None,
        "ranked_by": "change_1w_pct",
        "leaders": [r["sector"] for r in rows[:3]],
        "laggards": [r["sector"] for r in rows[-3:]][::-1],
        "sectors": rows,
        "errors": errors or None,
    }


def run_screen(**criteria: Any) -> dict:
    """Run the equity screener and normalize the rows to a compact shape."""
    raw = screener.screen(**criteria)
    results = [
        {
            "symbol": r.get("symbol"),
            "name": r.get("name"),
            "price": _num(r.get("price")),
            "percent_change": _num(r.get("percent_change")),
            "volume": _num(r.get("volume")),
            "market_cap": _num(r.get("market_cap")),
            "ma50": _num(r.get("ma50")),
            "ma200": _num(r.get("ma200")),
        }
        for r in raw
    ]
    return {"count": len(results), "criteria": {k: v for k, v in criteria.items() if v is not None},
            "results": results}
