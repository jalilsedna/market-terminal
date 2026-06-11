"""News Pulse (ROADMAP H14) — 24-hour news-driven directional read.

Monitors the terminal's existing news for a symbol and produces, for the
**current trading day only (24h horizon)**, a brief summary plus an opinion on
which way price may lean. Hybrid by design:

  * Deterministic layer (ALWAYS runs, no key, unit-tested): keyword polarity
    sentiment over the last 24h of headlines, blended with the symbol's
    technical bias and the macro regime → a baseline direction + confidence.
  * Analyst layer (optional): when an Anthropic key is configured, Claude reads
    the same package and reasons like a markets news analyst — a real prose
    summary, a sharpened 24h direction, catalysts, and caveats. Degrades to the
    deterministic read if the key/SDK/parse is unavailable.

Research synthesis, never a trade trigger. 24h horizon is deliberate — this is a
*today* read, not a forecast.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from obb_layer import llm
from services import analysis
from services import instruments as reg
from services import news as news_svc
from services.decision_brief import _infer_asset

DISCLAIMER = (
    "24-hour news-driven directional READ (sentiment + technicals + macro), "
    "research only — not a forecast, trade trigger, or order."
)

# Compact financial-polarity lexicons. Deliberately small and high-signal; this
# is a heuristic baseline, not an NLP model (that's the analyst layer's job).
_POSITIVE = {
    "beat", "beats", "surge", "surges", "jump", "jumps", "rally", "rallies", "soar", "soars",
    "upgrade", "upgrades", "upgraded", "raises", "raised", "record", "tops", "outperform",
    "strong", "bullish", "growth", "grows", "expands", "wins", "approval", "approved",
    "breakthrough", "gains", "gain", "rebound", "boost", "boosts", "buyback", "beat-and-raise",
    "guidance raise", "all-time high", "rises", "rose", "higher", "optimistic", "upbeat",
}
_NEGATIVE = {
    "miss", "misses", "missed", "plunge", "plunges", "drop", "drops", "fall", "falls", "slump",
    "slumps", "downgrade", "downgrades", "downgraded", "cuts", "cut", "loss", "losses", "weak",
    "bearish", "warns", "warning", "lawsuit", "probe", "investigation", "recall", "halts",
    "halt", "decline", "declines", "slashes", "disappoint", "disappoints", "fraud", "selloff",
    "sell-off", "tumble", "tumbles", "sinks", "sink", "lower", "concerns", "fears", "delays",
    "delay", "guidance cut", "all-time low", "bankruptcy", "default",
}

_LEAN = {1: "up", 0: "neutral", -1: "down"}


def _terms(blob: str, lexicon: set[str]) -> int:
    low = f" {blob.lower()} "
    return sum(1 for t in lexicon if f" {t} " in low or t in low)


def score_sentiment(headlines: list[dict]) -> dict:
    """Keyword-polarity sentiment over headlines (title + excerpt). Pure."""
    pos = neg = 0
    for h in headlines:
        blob = f"{h.get('title') or ''} {h.get('excerpt') or h.get('text') or ''}"
        pos += _terms(blob, _POSITIVE)
        neg += _terms(blob, _NEGATIVE)
    net = pos - neg
    lean = 1 if net >= 2 else -1 if net <= -2 else 0
    return {
        "positive": pos,
        "negative": neg,
        "score": net,
        "lean": _LEAN[lean],
        "headline_count": len(headlines),
    }


def _bias_to_points(bias: str | None) -> int:
    return {"long": 1, "up": 1, "short": -1, "down": -1}.get((bias or "").lower(), 0)


def _blend(news_lean: str, tech_bias: str | None) -> tuple[str, str]:
    """Combine news lean + technical bias into (direction, confidence)."""
    score = _bias_to_points(news_lean) + _bias_to_points(tech_bias)
    direction = "up" if score >= 1 else "down" if score <= -1 else "neutral"
    confidence = "high" if abs(score) >= 2 else "medium" if abs(score) == 1 else "low"
    # A flat-but-conflicting read (news up, tech down) lands neutral/low — correct.
    return direction, confidence


def _recent(headlines: list[dict], hours: int = 24) -> list[dict]:
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    out: list[dict] = []
    for h in headlines:
        raw = str(h.get("date") or "")[:19].replace(" ", "T")
        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            if dt >= cutoff:
                out.append(h)
        except (TypeError, ValueError):
            out.append(h)  # undated → keep (feed is already newest-first)
    return out or headlines[:8]


def _gather_headlines(symbol: str, asset: str, errors: dict) -> tuple[list[dict], Any]:
    inst = None
    try:
        inst = reg.resolve(symbol)
    except Exception:  # noqa: BLE001
        if asset in ("equity", "etf"):
            try:
                inst = reg.ensure(asset, symbol)
            except Exception:  # noqa: BLE001
                inst = None
    try:
        feed = news_svc.feed(instrument=inst.id, limit=12) if inst else news_svc.feed(limit=12)
        return _recent(feed.get("headlines") or []), inst
    except Exception as exc:  # noqa: BLE001
        errors["news"] = f"{type(exc).__name__}: {exc}"[:160]
        return [], inst


def _technical_bias(symbol: str, asset: str, errors: dict) -> str | None:
    try:
        if asset in ("equity", "etf"):
            from services import signals
            return (signals.trade_setup(symbol) or {}).get("bias")
        if asset in ("crypto", "forex"):
            from services import market_setup
            return (market_setup.market_setup(asset, symbol) or {}).get("bias")
    except Exception as exc:  # noqa: BLE001
        errors["technical"] = f"{type(exc).__name__}: {exc}"[:160]
    return None


_ANALYST_SYSTEM = (
    "You are a markets news analyst at a research desk. Given a symbol, the last "
    "24 hours of headlines, a baseline keyword-sentiment read, the symbol's "
    "technical bias, and the macro regime, reason like an analyst about how the "
    "news could shape price over the CURRENT TRADING DAY ONLY (next ~24h). Weigh "
    "catalysts against the technical and macro backdrop; note what could flip it. "
    "This is research, never advice or a trade signal. Respond with ONLY a JSON "
    "object (no prose, no code fences) with keys: summary (2-3 sentences), "
    "direction (one of 'up','down','neutral'), confidence (one of 'low','medium',"
    "'high'), catalysts (array of short strings), caveats (array of short strings)."
)


def _analyst_pass(symbol: str, asset: str, headlines: list[dict], sentiment: dict,
                  tech_bias: str | None, regime: str | None) -> dict | None:
    lines = [f"- {h.get('title')} ({h.get('source') or ''}, {str(h.get('date') or '')[:10]})"
             for h in headlines[:10]]
    user = (
        f"Symbol: {symbol} ({asset})\n"
        f"Macro regime: {regime or 'unknown'}\n"
        f"Technical bias: {tech_bias or 'unknown'}\n"
        f"Baseline news sentiment: {sentiment['lean']} "
        f"(+{sentiment['positive']}/-{sentiment['negative']} over {sentiment['headline_count']} headlines)\n"
        f"Headlines (last 24h, newest first):\n" + ("\n".join(lines) if lines else "(none)")
    )
    data = llm.analyze_json(_ANALYST_SYSTEM, user, max_tokens=900)
    if not isinstance(data, dict):
        return None
    direction = str(data.get("direction", "")).lower()
    if direction not in ("up", "down", "neutral"):
        direction = None
    confidence = str(data.get("confidence", "")).lower()
    if confidence not in ("low", "medium", "high"):
        confidence = None
    summary = data.get("summary")
    if not summary:
        return None
    cats = [str(x) for x in (data.get("catalysts") or [])][:6]
    cavs = [str(x) for x in (data.get("caveats") or [])][:6]
    return {"summary": str(summary), "direction": direction, "confidence": confidence,
            "catalysts": cats, "caveats": cavs}


def pulse(symbol: str, asset: str | None = None) -> dict:
    """24h news-driven directional read for one symbol (fault-tolerant)."""
    symbol = (symbol or "").strip()
    if not symbol:
        raise ValueError("symbol is required")
    asset = (asset or _infer_asset(symbol)).lower().strip()
    errors: dict[str, str] = {}

    headlines, _inst = _gather_headlines(symbol, asset, errors)
    sentiment = score_sentiment(headlines)
    tech_bias = _technical_bias(symbol, asset, errors)
    try:
        regime = (analysis.regime() or {}).get("regime")
    except Exception:  # noqa: BLE001
        regime = None

    base_dir, base_conf = _blend(sentiment["lean"], tech_bias)
    base_summary = (
        f"{symbol.upper()}: {sentiment['headline_count']} headlines in 24h, "
        f"sentiment {sentiment['lean']} (+{sentiment['positive']}/-{sentiment['negative']}); "
        f"technical {tech_bias or 'n/a'}; into a {regime or 'unclear'} macro → "
        f"24h lean {base_dir.upper()} ({base_conf})."
    )
    baseline = {"direction": base_dir, "confidence": base_conf, "summary": base_summary}

    engine = "rule-based"
    direction, confidence, summary = base_dir, base_conf, base_summary
    catalysts: list[str] = []
    caveats: list[str] = []
    if llm.enabled() and headlines:
        analyst = _analyst_pass(symbol, asset, headlines, sentiment, tech_bias, regime)
        if analyst:
            engine = "llm"
            direction = analyst["direction"] or base_dir
            confidence = analyst["confidence"] or base_conf
            summary = analyst["summary"]
            catalysts = analyst["catalysts"]
            caveats = analyst["caveats"]
        else:
            errors.setdefault("analyst", "LLM unavailable — using rule-based read")

    return {
        "symbol": symbol.upper(),
        "asset": asset,
        "horizon": "24h",
        "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
        "engine": engine,
        "direction": direction,
        "confidence": confidence,
        "summary": summary,
        "catalysts": catalysts,
        "caveats": caveats,
        "news_sentiment": sentiment,
        "technical_bias": tech_bias,
        "macro_regime": regime,
        "baseline": baseline,
        "headlines": headlines[:8],
        "errors": errors or None,
        "disclaimer": DISCLAIMER,
    }
