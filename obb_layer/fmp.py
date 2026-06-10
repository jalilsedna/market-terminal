"""Financial Modeling Prep (FMP) client — the fundamental brain (ROADMAP H).

A thin REST client over FMP's `stable` API. FMP also ships an MCP server, but we
consume **REST** here on purpose: it's the same data FMP's MCP proxies, and going
direct lets the terminal own caching (Starter is rate-capped), normalization,
fault-tolerance, and the interpreted "brain" — so Alice only ever sees the
terminal's *interpreted* output, never raw FMP.

OpenBB's `fmp` provider wraps only part of FMP; this client covers the full
surface incrementally (Phase 1 = company/statements/ratios/metrics/scores).
`httpx` is imported lazily; the key comes from config; **errors are sanitized so
the apikey can never leak**. Endpoint path strings are centralized in `_PATHS` so
a live 404 is a one-line fix.

This is a non-OpenBB provider client living in obb_layer — the same sanctioned
"OpenBB lacks it → extend here" pattern as `grouped.py`.
"""

from __future__ import annotations

from typing import Any

from cache.store import cached
from config import get_settings


class FmpDisabled(RuntimeError):
    """No FMP key configured (router → 503/degraded)."""


class FmpError(RuntimeError):
    """An FMP request failed — message is sanitized (never contains the key)."""


# Centralized FMP `stable` endpoint paths. If any 404s live, fix it here only.
_PATHS = {
    "profile": "profile",
    "peers": "stock-peers",
    "market_cap": "market-capitalization",
    "shares_float": "shares-float",
    "employee_count": "employee-count",
    "key_metrics": "key-metrics",
    "ratios": "ratios",
    "financial_scores": "financial-scores",
    "owner_earnings": "owner-earnings",
    "enterprise_values": "enterprise-values",
    "income": "income-statement",
    "balance": "balance-sheet-statement",
    "cash": "cash-flow-statement",
    "income_growth": "income-statement-growth",
    "financial_growth": "financial-growth",
    "revenue_geo": "revenue-geographic-segmentation",
    "revenue_product": "revenue-product-segmentation",
    # H2 — valuation / analyst / calendars
    "dcf": "discounted-cash-flow",
    "analyst_estimates": "analyst-estimates",
    "price_target": "price-target-consensus",
    "ratings": "ratings-snapshot",
    "earnings": "earnings",
    "dividends": "dividends",
}


def _get(path: str, **params: Any) -> Any:
    """GET an FMP endpoint, returning parsed JSON (list or dict). Raises
    FmpDisabled (no key) or FmpError (sanitized) on failure."""
    import httpx  # noqa: PLC0415 — lazy: only needed at fetch time

    settings = get_settings()
    key = settings.fmp_api_key
    if not key:
        raise FmpDisabled("FMP_API_KEY not set")
    url = f"{settings.fmp_base_url.rstrip('/')}/{path.lstrip('/')}"
    query = {k: v for k, v in params.items() if v is not None}
    query["apikey"] = key
    try:
        resp = httpx.get(url, params=query, timeout=30.0)
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # Never echo the URL (it carries apikey) — status code only.
        raise FmpError(f"{path}: HTTP {exc.response.status_code}") from None
    except httpx.HTTPError as exc:
        raise FmpError(f"{path}: {type(exc).__name__}") from None
    return resp.json()


# --- Phase 1: company / statements / ratios / metrics / scores ------------- #
@cached("profile")
def profile(symbol: str) -> Any:
    return _get(_PATHS["profile"], symbol=symbol)


@cached("fundamentals")
def peers(symbol: str) -> Any:
    return _get(_PATHS["peers"], symbol=symbol)


@cached("fundamentals")
def market_cap(symbol: str) -> Any:
    return _get(_PATHS["market_cap"], symbol=symbol)


@cached("fundamentals")
def shares_float(symbol: str) -> Any:
    return _get(_PATHS["shares_float"], symbol=symbol)


@cached("fundamentals")
def employee_count(symbol: str) -> Any:
    return _get(_PATHS["employee_count"], symbol=symbol, limit=1)


@cached("fundamentals")
def key_metrics(symbol: str, period: str = "annual", limit: int = 5) -> Any:
    return _get(_PATHS["key_metrics"], symbol=symbol, period=period, limit=limit)


@cached("fundamentals")
def ratios(symbol: str, period: str = "annual", limit: int = 5) -> Any:
    return _get(_PATHS["ratios"], symbol=symbol, period=period, limit=limit)


@cached("fundamentals")
def financial_scores(symbol: str) -> Any:
    return _get(_PATHS["financial_scores"], symbol=symbol)


@cached("fundamentals")
def owner_earnings(symbol: str, limit: int = 5) -> Any:
    return _get(_PATHS["owner_earnings"], symbol=symbol, limit=limit)


@cached("fundamentals")
def enterprise_values(symbol: str, limit: int = 5) -> Any:
    return _get(_PATHS["enterprise_values"], symbol=symbol, limit=limit)


@cached("fundamentals")
def income_statement(symbol: str, period: str = "annual", limit: int = 5) -> Any:
    return _get(_PATHS["income"], symbol=symbol, period=period, limit=limit)


@cached("fundamentals")
def balance_sheet(symbol: str, period: str = "annual", limit: int = 5) -> Any:
    return _get(_PATHS["balance"], symbol=symbol, period=period, limit=limit)


@cached("fundamentals")
def cash_flow(symbol: str, period: str = "annual", limit: int = 5) -> Any:
    return _get(_PATHS["cash"], symbol=symbol, period=period, limit=limit)


@cached("fundamentals")
def income_growth(symbol: str, period: str = "annual", limit: int = 5) -> Any:
    return _get(_PATHS["income_growth"], symbol=symbol, period=period, limit=limit)


@cached("fundamentals")
def revenue_geo(symbol: str) -> Any:
    return _get(_PATHS["revenue_geo"], symbol=symbol)


@cached("fundamentals")
def revenue_product(symbol: str) -> Any:
    return _get(_PATHS["revenue_product"], symbol=symbol)


# --- H2: valuation (DCF) / analyst / calendars ----------------------------- #
@cached("estimates")
def dcf(symbol: str) -> Any:
    return _get(_PATHS["dcf"], symbol=symbol)


@cached("estimates")
def analyst_estimates(symbol: str, period: str = "annual", limit: int = 4) -> Any:
    return _get(_PATHS["analyst_estimates"], symbol=symbol, period=period, limit=limit)


@cached("estimates")
def price_target_consensus(symbol: str) -> Any:
    return _get(_PATHS["price_target"], symbol=symbol)


@cached("estimates")
def ratings_snapshot(symbol: str) -> Any:
    return _get(_PATHS["ratings"], symbol=symbol)


@cached("calendar")
def earnings(symbol: str, limit: int = 8) -> Any:
    return _get(_PATHS["earnings"], symbol=symbol, limit=limit)


@cached("calendar")
def dividends(symbol: str, limit: int = 4) -> Any:
    return _get(_PATHS["dividends"], symbol=symbol, limit=limit)
