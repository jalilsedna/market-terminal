"""V3 — News Feed domain logic (SPEC.md §4 V3).

Two modes, auto-selected by what keys are configured:

* **World wire (preferred):** if a paid news provider key is set (FMP / Benzinga /
  Tiingo / Intrinio), the feed is a real macro/markets wire via `news.world`,
  deduped and tagged with macro themes + the watchlist instruments mentioned.
* **Proxy fallback (keyless):** with no news key, OpenBB's *world* news 402s, so the
  feed is assembled from free per-instrument `news.company` (yfinance) on liquid
  ETF proxies (GLD/QQQ/DIA/FXE/FXB), merged and deduped.

So the terminal degrades gracefully with no keys and *upgrades automatically* the
moment a news key is added — no config flip. Per-instrument requests always use
the free yfinance company-news path. Services never import OpenBB directly.
"""

from __future__ import annotations

from collections.abc import Sequence

from concurrency import parallel_map
from config import get_settings
from obb_layer import news
from obb_layer.symbols import WATCHLIST

# Cross-instrument macro themes (tagged as "macro" when matched in title/excerpt).
MACRO_KEYWORDS: list[str] = [
    "fed", "fomc", "powell", "interest rate", "rate cut", "rate hike", "inflation",
    "cpi", "pce", "treasury", "yield", "payroll", "nonfarm", "jobs report",
    "unemployment", "gdp", "recession", "tariff", "dollar", "central bank",
]

# Light keyword map to tag world-wire headlines with our watchlist instruments.
_INSTRUMENT_KEYWORDS: dict[str, list[str]] = {
    "GC": ["gold", "bullion"],
    "NQ": ["nasdaq", "tech stocks", "big tech"],
    "YM": ["dow jones", "dow industrial"],
    "6E": ["euro", "ecb", "eurozone"],
    "6B": ["pound", "sterling", "boe", "bank of england"],
}

# Providers (in priority order) whose key unlocks OpenBB's *world* news.
_WORLD_PROVIDERS: tuple[tuple[str, str], ...] = (
    ("fmp", "fmp_api_key"),
    ("benzinga", "benzinga_api_key"),
    ("tiingo", "tiingo_api_key"),
    ("intrinio", "intrinio_api_key"),
)


def _world_provider() -> str | None:
    """First configured world-news provider, or None → use the proxy feed."""
    settings = get_settings()
    for provider, attr in _WORLD_PROVIDERS:
        if getattr(settings, attr, None):
            return provider
    return None


def _macro_tagged(blob: str) -> bool:
    return any(w in blob for w in MACRO_KEYWORDS)


def _excerpt(item: dict) -> str | None:
    return item.get("excerpt") or item.get("text") or item.get("body")


def _proxy_headline(item: dict, instrument: str) -> dict:
    tags = [instrument]
    blob = f"{item.get('title') or ''} {_excerpt(item) or ''}".lower()
    if _macro_tagged(blob):
        tags.append("macro")
    return {
        "date": str(item.get("date")) if item.get("date") else None,
        "title": item.get("title"),
        "source": item.get("source"),
        "url": item.get("url"),
        "excerpt": _excerpt(item),
        "tags": tags,
    }


def _world_headline(item: dict) -> dict:
    """Tag a world-wire item with 'macro' and any watchlist instruments mentioned."""
    excerpt = _excerpt(item)
    blob = f"{item.get('title') or ''} {excerpt or ''}".lower()
    tags: list[str] = []
    if _macro_tagged(blob):
        tags.append("macro")
    tags += [code for code, kws in _INSTRUMENT_KEYWORDS.items() if any(k in blob for k in kws)]
    return {
        "date": str(item.get("date")) if item.get("date") else None,
        "title": item.get("title"),
        "source": item.get("source") or item.get("site"),
        "url": item.get("url"),
        "excerpt": excerpt,
        "tags": tags,
    }


def _dedupe_sorted(headlines: Sequence[dict], limit: int) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for h in headlines:
        key = (h["url"] or h["title"] or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(h)
    out.sort(key=lambda h: h["date"] or "", reverse=True)
    return out[:limit]


def _world_feed(limit: int, provider: str) -> dict:
    """A real macro/markets wire via news.world (needs a provider key)."""
    raw = news.world_news(provider=provider, limit=max(limit * 2, 50))
    headlines = _dedupe_sorted([_world_headline(i) for i in raw], limit)
    return {
        "count": len(headlines),
        "provider": provider,
        "filter": "world",
        "sources": {"world": provider},
        "errors": None,
        "headlines": headlines,
    }


def _proxy_feed(limit: int, targets: dict, provider: str) -> dict:
    """Free fallback: per-instrument yfinance company news, merged + tag-deduped."""
    per_instrument = max(limit, 20)
    seen: set[str] = set()
    headlines: list[dict] = []
    errors: dict[str, str] = {}

    def _fetch(item):
        code, inst = item
        try:
            return code, news.company_news(inst.news_symbol, provider=provider, limit=per_instrument), None
        except Exception as exc:  # noqa: BLE001 — one ticker must not sink the feed
            return code, [], type(exc).__name__

    for code, raw, err in parallel_map(_fetch, targets.items()):
        if err:
            errors[code] = err
            continue
        for item in raw:
            h = _proxy_headline(item, code)
            dedupe_key = (h["url"] or h["title"] or "").strip().lower()
            if not dedupe_key:
                continue
            if dedupe_key in seen:
                for existing in headlines:  # same story under another instrument → merge tag
                    if (existing["url"] or existing["title"] or "").strip().lower() == dedupe_key:
                        if code not in existing["tags"]:
                            existing["tags"].append(code)
                        break
                continue
            seen.add(dedupe_key)
            headlines.append(h)

    if not headlines and errors:
        raise RuntimeError(f"all news fetches failed (e.g. {next(iter(errors.values()))})")

    headlines.sort(key=lambda h: h["date"] or "", reverse=True)
    return {
        "count": len(headlines[:limit]),
        "provider": provider,
        "filter": "watchlist",
        "sources": {code: inst.news_symbol for code, inst in targets.items()},
        "errors": errors or None,
        "headlines": headlines[:limit],
    }


def feed(*, limit: int = 50, instrument: str | None = None, provider: str = "yfinance") -> dict:
    """Merged, tagged, deduped news feed (newest first).

    Uses a real world wire when a news-provider key is set; otherwise the free
    yfinance per-instrument proxy feed. Per-instrument requests always use the
    proxy path (free, symbol-tagged).
    """
    if instrument:
        key = instrument.upper()
        if key not in WATCHLIST:
            raise ValueError(f"unknown instrument '{instrument}'; known: {', '.join(WATCHLIST)}")
        return _proxy_feed(limit, {key: WATCHLIST[key]}, provider)

    world_provider = _world_provider()
    if world_provider:
        try:
            return _world_feed(limit, world_provider)
        except Exception:  # noqa: BLE001 — world wire failed → fall back to the free proxy feed
            pass
    return _proxy_feed(limit, dict(WATCHLIST), provider)
