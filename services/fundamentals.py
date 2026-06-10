"""Fundamentals view (ROADMAP H, Phase 1) — the terminal's bottom-up brain.

Composes a per-ticker fundamentals dashboard from FMP: company profile, valuation,
quality/health, growth, statement highlights, peers, and revenue segmentation.

Built fault-tolerant like the macro dashboard — each block fetches independently,
so an FMP tier-gated or failed endpoint degrades to an `errors` entry instead of
breaking the view. Field extraction is **defensive** (`_pick` tries several FMP
field-name variants) because FMP's keys differ a little across plans/versions; the
raw values are kept so we can lock names once we see live responses. The
interpreted "fundamental read" verdict comes in Phase 2.
"""

from __future__ import annotations

from typing import Any

from obb_layer import fmp


def _first(x: Any) -> dict:
    """FMP endpoints return a list; take the most recent (first) record."""
    if isinstance(x, list):
        return x[0] if x else {}
    return x if isinstance(x, dict) else {}


def _pick(d: dict, *keys: str) -> Any:
    """First present, non-None value among `keys` (FMP name variants)."""
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return None


def _profile(p: dict) -> dict:
    return {
        "name": _pick(p, "companyName", "name"),
        "sector": _pick(p, "sector"),
        "industry": _pick(p, "industry"),
        "exchange": _pick(p, "exchangeShortName", "exchange"),
        "price": _pick(p, "price"),
        "market_cap": _pick(p, "marketCap", "mktCap"),
        "beta": _pick(p, "beta"),
        "currency": _pick(p, "currency"),
        "ceo": _pick(p, "ceo"),
        "employees": _pick(p, "fullTimeEmployees"),
        "country": _pick(p, "country"),
        "website": _pick(p, "website"),
        "description": _pick(p, "description"),
    }


def _valuation(ratios: dict, metrics: dict) -> dict:
    return {
        # stable API uses priceToEarningsRatio; keep v3 names as fallbacks.
        "pe": _pick(ratios, "priceToEarningsRatio", "priceEarningsRatio", "peRatio") or _pick(metrics, "peRatio", "priceToEarningsRatioTTM"),
        "ps": _pick(ratios, "priceToSalesRatio", "priceSalesRatio") or _pick(metrics, "priceToSalesRatio"),
        "pb": _pick(ratios, "priceToBookRatio", "pbRatio") or _pick(metrics, "pbRatio"),
        "ev_ebitda": _pick(ratios, "enterpriseValueMultiple", "evToEbitda") or _pick(metrics, "evToEBITDA", "enterpriseValueOverEBITDA"),
        "dividend_yield": _pick(ratios, "dividendYield") or _pick(metrics, "dividendYield"),
        "fcf_yield": _pick(metrics, "freeCashFlowYield"),
        "earnings_yield": _pick(metrics, "earningsYield"),
    }


def _quality(ratios: dict, metrics: dict, scores: dict) -> dict:
    return {
        "piotroski": _pick(scores, "piotroskiScore"),
        "altman_z": _pick(scores, "altmanZScore"),
        "roe": _pick(ratios, "returnOnEquity") or _pick(metrics, "roe", "returnOnEquity"),
        "roic": _pick(metrics, "roic", "returnOnInvestedCapital"),
        "net_margin": _pick(ratios, "netProfitMargin"),
        "gross_margin": _pick(ratios, "grossProfitMargin"),
        "operating_margin": _pick(ratios, "operatingProfitMargin"),
        "current_ratio": _pick(ratios, "currentRatio") or _pick(metrics, "currentRatio"),
        # stable API uses debtToEquityRatio; keep v3 names as fallbacks.
        "debt_to_equity": _pick(ratios, "debtToEquityRatio", "debtEquityRatio", "debtToEquity") or _pick(metrics, "debtToEquityRatio", "debtToEquity"),
    }


def _growth(g: dict) -> dict:
    return {
        "revenue": _pick(g, "growthRevenue", "revenueGrowth"),
        "eps": _pick(g, "growthEPS", "epsgrowth", "growthEPSDiluted"),
        "net_income": _pick(g, "growthNetIncome"),
        "fiscal_year": _pick(g, "date", "calendarYear"),
    }


def _segments(rows: Any) -> dict | None:
    """Latest revenue segmentation record ({segment: value}), if available."""
    rec = _first(rows)
    # FMP returns {date:..., <segment>: value, ...} or nested under a key.
    seg = {k: v for k, v in rec.items() if k not in ("date", "symbol", "period") and isinstance(v, (int, float))}
    return seg or None


def dashboard(symbol: str) -> dict:
    """Per-ticker fundamentals dashboard. Fault-tolerant: failed/gated FMP blocks
    land in `errors` rather than raising."""
    symbol = symbol.upper().strip()
    errors: dict[str, str] = {}

    def grab(name: str, fn):
        try:
            return fn()
        except fmp.FmpDisabled:
            errors[name] = "FMP not configured"
        except fmp.FmpError as exc:
            errors[name] = str(exc)
        except Exception as exc:  # noqa: BLE001 — never let one block break the view
            errors[name] = f"{type(exc).__name__}"
        return None

    profile = _first(grab("profile", lambda: fmp.profile(symbol)) or [])
    ratios = _first(grab("ratios", lambda: fmp.ratios(symbol, limit=1)) or [])
    metrics = _first(grab("key_metrics", lambda: fmp.key_metrics(symbol, limit=1)) or [])
    scores = _first(grab("scores", lambda: fmp.financial_scores(symbol)) or [])
    growth = _first(grab("growth", lambda: fmp.income_growth(symbol, limit=1)) or [])
    peers_raw = grab("peers", lambda: fmp.peers(symbol)) or []
    geo = grab("revenue_geo", lambda: fmp.revenue_geo(symbol))
    product = grab("revenue_product", lambda: fmp.revenue_product(symbol))

    peers = _first(peers_raw).get("peersList") if peers_raw else None
    if peers is None and isinstance(peers_raw, list):
        peers = [p.get("symbol") for p in peers_raw if isinstance(p, dict) and p.get("symbol")]

    return {
        "symbol": symbol,
        "enabled": True,
        "profile": _profile(profile),
        "valuation": _valuation(ratios, metrics),
        "quality": _quality(ratios, metrics, scores),
        "growth": _growth(growth),
        "peers": peers or [],
        "segmentation": {"geographic": _segments(geo), "product": _segments(product)},
        "errors": errors or None,
        "disclaimer": "Fundamental research context (FMP) — not investment advice or a trade trigger.",
    }
