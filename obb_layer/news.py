"""OpenBB + FMP data functions for V3 — News Feed (SPEC.md §4 V3).

World news via keyed OpenBB providers (default fmp). Company/symbol news via FMP
REST (`obb_layer/fmp.py`) — no Yahoo path.
"""

from __future__ import annotations

from typing import Any

from cache.store import cached
from circuit import guarded
from obb_layer.client import get_obb
from obb_layer.normalize import to_records


def _normalize_fmp_news(rows: list[dict[str, Any]]) -> list[dict]:
    out: list[dict] = []
    for item in rows:
        out.append({
            "date": item.get("publishedDate") or item.get("date"),
            "title": item.get("title"),
            "source": item.get("site") or item.get("source"),
            "url": item.get("url"),
            "excerpt": item.get("text") or item.get("body"),
        })
    return out


@cached("news")
@guarded()
def world_news(provider: str = "fmp", limit: int = 100) -> list[dict]:
    """Latest world/macro financial news. Provider needs a key (default: fmp)."""
    obb = get_obb()
    return to_records(obb.news.world(provider=provider, limit=limit), sort_by_date=False)


@cached("news")
@guarded()
def company_news(symbol: str, provider: str = "fmp", limit: int = 50) -> list[dict]:
    """Symbol-tagged company news via FMP."""
    if provider != "fmp":
        raise ValueError(f"unsupported news provider {provider!r}; use fmp")
    from obb_layer import fmp

    payload = fmp.stock_news(symbol, limit=limit)
    if isinstance(payload, list):
        return _normalize_fmp_news([r for r in payload if isinstance(r, dict)])
    if isinstance(payload, dict):
        return _normalize_fmp_news([payload])
    return []
