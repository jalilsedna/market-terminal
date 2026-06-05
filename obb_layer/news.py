"""OpenBB data functions for V3 — News Feed (SPEC.md §4 V3).

Thin fetch→normalize→cache wrappers over OpenBB news. World news runs on the
providers available in this OpenBB version (benzinga/fmp/intrinio/tiingo —
keyed); company news additionally supports free yfinance.

News is cached with a short TTL (`news`) so the feed stays fresh without
hammering the provider.
"""

from __future__ import annotations

from cache.store import cached
from obb_layer.client import get_obb
from obb_layer.normalize import to_records


@cached("news")
def world_news(provider: str = "fmp", limit: int = 100) -> list[dict]:
    """Latest world/macro financial news. Provider needs a key (default: fmp)."""
    obb = get_obb()
    return to_records(obb.news.world(provider=provider, limit=limit), sort_by_date=False)


@cached("news")
def company_news(symbol: str, provider: str = "yfinance", limit: int = 50) -> list[dict]:
    """Symbol-tagged company news (provider 'yfinance' is free)."""
    obb = get_obb()
    return to_records(
        obb.news.company(symbol=symbol, provider=provider, limit=limit), sort_by_date=False
    )
