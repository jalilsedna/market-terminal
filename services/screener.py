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


def run_screen(
    *,
    sector: str | None = None,
    industry: str | None = None,
    exchange: str | None = None,
    country: str | None = None,
    mktcap_min: float | None = None,
    mktcap_max: float | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    volume_min: float | None = None,
    beta_min: float | None = None,
    beta_max: float | None = None,
    dividend_min: float | None = None,
    actively_trading: bool | None = True,
    limit: int = 50,
) -> dict:
    """Fundamental equity screener (FMP `company-screener`, direct REST).

    Filters the universe by cap / price / beta / dividend / volume / sector /
    industry / exchange / country and normalizes the rows. Fault-tolerant: a
    provider/tier failure surfaces in `error` rather than raising.
    """
    from config import get_settings
    from obb_layer import fmp
    if not get_settings().fmp_enabled:
        return {"enabled": False, "count": 0, "results": [],
                "error": "Screener needs an FMP key — set FMP_API_KEY."}

    fmp_filters = {
        "marketCapMoreThan": mktcap_min, "marketCapLowerThan": mktcap_max,
        "priceMoreThan": price_min, "priceLowerThan": price_max,
        "volumeMoreThan": volume_min, "betaMoreThan": beta_min, "betaLowerThan": beta_max,
        "dividendMoreThan": dividend_min, "sector": sector, "industry": industry,
        "exchange": exchange, "country": country,
        "isActivelyTrading": actively_trading, "limit": max(1, min(limit, 1000)),
    }
    criteria = {k: v for k, v in {
        "sector": sector, "industry": industry, "exchange": exchange, "country": country,
        "mktcap_min": mktcap_min, "mktcap_max": mktcap_max, "price_min": price_min,
        "price_max": price_max, "volume_min": volume_min, "beta_min": beta_min,
        "beta_max": beta_max, "dividend_min": dividend_min,
    }.items() if v is not None}

    try:
        raw = fmp.company_screener(**fmp_filters)
    except fmp.FmpError as exc:
        return {"enabled": True, "count": 0, "results": [], "criteria": criteria, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"enabled": True, "count": 0, "results": [], "criteria": criteria,
                "error": f"{type(exc).__name__}: {exc}"[:160]}

    results = [
        {
            "symbol": r.get("symbol"),
            "name": r.get("companyName") or r.get("name"),
            "price": _num(r.get("price")),
            "market_cap": _num(r.get("marketCap")),
            "beta": _num(r.get("beta")),
            "dividend": _num(r.get("lastAnnualDividend")),
            "volume": _num(r.get("volume")),
            "sector": r.get("sector"),
            "industry": r.get("industry"),
            "exchange": r.get("exchangeShortName") or r.get("exchange"),
        }
        for r in (raw if isinstance(raw, list) else [])
    ]
    results.sort(key=lambda x: (x.get("market_cap") is not None, x.get("market_cap") or 0), reverse=True)
    return {"enabled": True, "count": len(results), "criteria": criteria, "results": results}
