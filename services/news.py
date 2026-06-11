"""News Feed — merged headlines tagged to tracked instruments.

World wire when a news-provider key is set; otherwise per-instrument FMP company
news on symbols in the registry. Services never import OpenBB directly.
"""

from __future__ import annotations

from collections.abc import Sequence

from concurrency import parallel_map
from config import get_settings
from obb_layer import news
from obb_layer.symbol_map import map_symbol
from services import instruments as reg

MACRO_KEYWORDS: list[str] = [
    "fed", "fomc", "powell", "interest rate", "rate cut", "rate hike", "inflation",
    "cpi", "pce", "treasury", "yield", "payroll", "nonfarm", "jobs report",
    "unemployment", "gdp", "recession", "tariff", "dollar", "central bank",
]

_WORLD_PROVIDERS: tuple[tuple[str, str], ...] = (
    ("fmp", "fmp_api_key"),
    ("benzinga", "benzinga_api_key"),
    ("tiingo", "tiingo_api_key"),
    ("intrinio", "intrinio_api_key"),
)


def _world_provider() -> str | None:
    settings = get_settings()
    for provider, attr in _WORLD_PROVIDERS:
        if getattr(settings, attr, None):
            return provider
    return None


def _macro_tagged(blob: str) -> bool:
    return any(w in blob for w in MACRO_KEYWORDS)


def _excerpt(item: dict) -> str | None:
    return item.get("excerpt") or item.get("text") or item.get("body")


def _news_ticker(inst: reg.TrackedInstrument) -> str | None:
    if inst.meta.get("news_symbol"):
        return inst.meta["news_symbol"]
    if inst.asset in ("equity", "etf"):
        return inst.symbol
    if inst.asset == "crypto":
        return map_symbol("crypto", inst.symbol, "fmp") or inst.symbol.replace("-", "")
    return None


def _keyword_map() -> dict[str, list[str]]:
    """Build headline→instrument tags from the live registry."""
    out: dict[str, list[str]] = {}
    for inst in reg.list_all():
        key = inst.code or inst.id
        words = {inst.label.lower(), inst.symbol.lower(), key.lower()}
        if inst.meta.get("name"):
            words.add(str(inst.meta["name"]).lower())
        if inst.asset == "futures":
            words.add(inst.symbol.lower().replace("=f", ""))
            if key == "GC":
                words.update({"gold", "bullion"})
        if inst.asset == "crypto" and "-" in inst.symbol:
            words.add(inst.symbol.split("-")[0].lower())
        out[key] = [w for w in words if len(w) >= 2]
    return out


def _proxy_headline(item: dict, tag: str) -> dict:
    tags = [tag]
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
    excerpt = _excerpt(item)
    blob = f"{item.get('title') or ''} {excerpt or ''}".lower()
    tags: list[str] = []
    if _macro_tagged(blob):
        tags.append("macro")
    for code, kws in _keyword_map().items():
        if any(k in blob for k in kws):
            tags.append(code)
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


def _proxy_feed(limit: int, targets: dict[str, reg.TrackedInstrument], provider: str) -> dict:
    if not targets:
        return {
            "count": 0,
            "provider": provider,
            "filter": "registry",
            "sources": {},
            "errors": None,
            "headlines": [],
        }
    per_instrument = max(limit, 20)
    seen: set[str] = set()
    headlines: list[dict] = []
    errors: dict[str, str] = {}

    def _fetch(item):
        tag, inst = item
        ticker = _news_ticker(inst)
        if not ticker:
            return tag, [], "no news symbol"
        try:
            return tag, news.company_news(ticker, provider=provider, limit=per_instrument), None
        except Exception as exc:  # noqa: BLE001
            return tag, [], type(exc).__name__

    def _crypto_world_fallback(tag: str, inst: reg.TrackedInstrument) -> list[dict]:
        """When FMP stock news has no crypto rows, mine the world wire by keyword."""
        if inst.asset != "crypto":
            return []
        wp = _world_provider()
        if not wp:
            return []
        kws = _keyword_map().get(tag, [])
        if not kws:
            return []
        try:
            world = news.world_news(provider=wp, limit=max(per_instrument * 3, 60))
        except Exception:  # noqa: BLE001
            return []
        out: list[dict] = []
        for item in world:
            blob = f"{item.get('title') or ''} {_excerpt(item) or ''}".lower()
            if any(k in blob for k in kws):
                out.append(item)
        return out

    for tag, raw, err in parallel_map(_fetch, targets.items()):
        if err:
            errors[tag] = err
            continue
        inst = targets[tag]
        if not raw and inst.asset == "crypto":
            raw = _crypto_world_fallback(tag, inst)
        for item in raw:
            h = _proxy_headline(item, tag)
            dedupe_key = (h["url"] or h["title"] or "").strip().lower()
            if not dedupe_key:
                continue
            if dedupe_key in seen:
                for existing in headlines:
                    if (existing["url"] or existing["title"] or "").strip().lower() == dedupe_key:
                        if tag not in existing["tags"]:
                            existing["tags"].append(tag)
                        break
                continue
            seen.add(dedupe_key)
            headlines.append(h)

    if not headlines and errors and len(errors) == len(targets):
        raise RuntimeError(f"all news fetches failed (e.g. {next(iter(errors.values()))})")

    headlines.sort(key=lambda h: h["date"] or "", reverse=True)
    return {
        "count": len(headlines[:limit]),
        "provider": provider,
        "filter": "registry",
        "sources": {tag: _news_ticker(inst) for tag, inst in targets.items()},
        "errors": errors or None,
        "headlines": headlines[:limit],
    }


def feed(*, limit: int = 50, instrument: str | None = None, provider: str = "fmp") -> dict:
    """Merged, tagged, deduped news feed (newest first)."""
    if instrument:
        inst = reg.resolve(instrument)
        tag = inst.code or inst.id
        return _proxy_feed(limit, {tag: inst}, provider)

    world_provider = _world_provider()
    if world_provider:
        try:
            return _world_feed(limit, world_provider)
        except Exception:  # noqa: BLE001
            pass
    return _proxy_feed(limit, reg.news_wire_targets(), provider)
