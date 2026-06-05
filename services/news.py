"""V3 — News Feed domain logic (SPEC.md §4 V3).

OpenBB's *world* news providers (benzinga/fmp/intrinio/tiingo) all need a paid
key in this version (FMP's free tier returns 402). The only free news source is
`news.company` via **yfinance** — so the feed is assembled from per-instrument
news on liquid ETF proxies (GLD/QQQ/DIA/FXE/FXB), then merged, deduped, and
sorted newest-first. Each headline is tagged with the instrument it came from
plus any macro theme matched in its text.

Services never import OpenBB directly — they call `obb_layer/`.
"""

from __future__ import annotations

from obb_layer import news
from obb_layer.symbols import WATCHLIST

# Cross-instrument macro themes (tagged as "macro" when matched in title/excerpt).
MACRO_KEYWORDS: list[str] = [
    "fed", "fomc", "powell", "interest rate", "rate cut", "rate hike", "inflation",
    "cpi", "pce", "treasury", "yield", "payroll", "nonfarm", "jobs report",
    "unemployment", "gdp", "recession", "tariff", "dollar", "central bank",
]


def _macro_tagged(item: dict) -> bool:
    blob = f"{item.get('title') or ''} {item.get('excerpt') or ''}".lower()
    return any(w in blob for w in MACRO_KEYWORDS)


def _headline(item: dict, instrument: str) -> dict:
    tags = [instrument]
    if _macro_tagged(item):
        tags.append("macro")
    return {
        "date": str(item.get("date")) if item.get("date") else None,
        "title": item.get("title"),
        "source": item.get("source"),
        "url": item.get("url"),
        "excerpt": item.get("excerpt"),
        "tags": tags,
    }


def feed(*, limit: int = 50, instrument: str | None = None, provider: str = "yfinance") -> dict:
    """Merged, tagged, deduped news feed (newest first) from free yfinance news."""
    if instrument:
        key = instrument.upper()
        if key not in WATCHLIST:
            raise ValueError(f"unknown instrument '{instrument}'; known: {', '.join(WATCHLIST)}")
        targets = {key: WATCHLIST[key]}
    else:
        targets = dict(WATCHLIST)

    per_instrument = max(limit, 20)
    seen: set[str] = set()
    headlines: list[dict] = []
    errors: dict[str, str] = {}

    for code, inst in targets.items():
        try:
            raw = news.company_news(inst.news_symbol, provider=provider, limit=per_instrument)
        except Exception as exc:  # noqa: BLE001 — one ticker must not sink the feed
            errors[code] = f"{type(exc).__name__}"
            continue
        for item in raw:
            h = _headline(item, code)
            dedupe_key = (h["url"] or h["title"] or "").strip().lower()
            if not dedupe_key:
                continue
            if dedupe_key in seen:
                # Same story surfaced under another instrument → merge the tag.
                for existing in headlines:
                    if (existing["url"] or existing["title"] or "").strip().lower() == dedupe_key:
                        if code not in existing["tags"]:
                            existing["tags"].append(code)
                        break
                continue
            seen.add(dedupe_key)
            headlines.append(h)

    # If every target errored and nothing came back, surface it as a failure.
    if not headlines and errors:
        raise RuntimeError(f"all news fetches failed (e.g. {next(iter(errors.values()))})")

    headlines.sort(key=lambda h: h["date"] or "", reverse=True)
    headlines = headlines[:limit]

    return {
        "count": len(headlines),
        "provider": provider,
        "filter": (instrument.upper() if instrument else "watchlist"),
        "sources": {code: inst.news_symbol for code, inst in targets.items()},
        "errors": errors or None,
        "headlines": headlines,
    }
