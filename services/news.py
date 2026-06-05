"""V3 — News Feed domain logic (SPEC.md §4 V3).

Pulls world/macro news, normalizes to a uniform headline shape, dedupes, sorts
newest-first, and tags each headline with the watchlist instrument(s) and/or
macro themes it plausibly affects (SPEC §4 V3). By default the feed is filtered
to headlines that match the watchlist or a macro keyword — the trader's signal,
not the firehose.

Services never import OpenBB directly — they call `obb_layer/`.
"""

from __future__ import annotations

from typing import Any

from obb_layer import news
from obb_layer.symbols import WATCHLIST

# Instrument shorthand -> keywords that plausibly move it (matched case-insensitively
# against title + excerpt). Kept here as the one explicit news-tagging map.
INSTRUMENT_KEYWORDS: dict[str, list[str]] = {
    "6E": ["euro", "eur/usd", "eurusd", "ecb", "eurozone", "lagarde", "european central bank"],
    "6B": ["pound", "sterling", "gbp", "boe", "bank of england", "britain", "uk ", "united kingdom"],
    "GC": ["gold", "xau", "bullion", "precious metal"],
    "NQ": ["nasdaq", "ndx", "tech stocks", "technology stocks", "big tech"],
    "YM": ["dow jones", "djia", "industrial average", "blue chip"],
}

# Cross-instrument macro themes (tagged as "macro").
MACRO_KEYWORDS: list[str] = [
    "fed", "fomc", "powell", "interest rate", "rate cut", "rate hike", "inflation",
    "cpi", "pce", "treasury", "yield", "payroll", "nonfarm", "jobs report",
    "unemployment", "gdp", "recession", "tariff", "dollar", "central bank",
]


def _text(item: dict) -> str:
    return f"{item.get('title') or ''} {item.get('excerpt') or ''}".lower()


def _tags(item: dict) -> list[str]:
    """Instruments + 'macro' a headline plausibly affects."""
    blob = _text(item)
    tags = [code for code, words in INSTRUMENT_KEYWORDS.items() if any(w in blob for w in words)]
    if any(w in blob for w in MACRO_KEYWORDS):
        tags.append("macro")
    return tags


def _headline(item: dict) -> dict:
    return {
        "date": str(item.get("date")) if item.get("date") else None,
        "title": item.get("title"),
        "source": item.get("source"),
        "url": item.get("url"),
        "excerpt": item.get("excerpt"),
        "tags": _tags(item),
    }


def feed(
    *,
    limit: int = 50,
    relevant_only: bool = True,
    instrument: str | None = None,
    provider: str = "fmp",
) -> dict:
    """Build the merged, tagged, deduped news feed (newest first)."""
    # Validate instrument up front so bad input fails fast, before any network call.
    instrument_key: str | None = None
    if instrument:
        instrument_key = instrument.upper()
        if instrument_key not in WATCHLIST:
            raise ValueError(f"unknown instrument '{instrument}'; known: {', '.join(WATCHLIST)}")

    raw = news.world_news(provider=provider, limit=max(limit * 3, 100))

    seen: set[str] = set()
    headlines: list[dict] = []
    for item in raw:
        h = _headline(item)
        dedupe_key = (h["url"] or h["title"] or "").strip().lower()
        if not dedupe_key or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        headlines.append(h)

    if instrument_key:
        headlines = [h for h in headlines if instrument_key in h["tags"]]
    elif relevant_only:
        headlines = [h for h in headlines if h["tags"]]

    headlines.sort(key=lambda h: h["date"] or "", reverse=True)
    headlines = headlines[:limit]

    return {
        "count": len(headlines),
        "provider": provider,
        "filter": instrument_key or ("relevant_only" if relevant_only else "all"),
        "headlines": headlines,
    }
