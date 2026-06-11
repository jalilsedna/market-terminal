"""Decision brief (ROADMAP H8) — the one-call research package for Alice.

Fuses EVERYTHING the terminal produces for a single symbol into one structured,
asset-routed response, so the execution agent gets the complete picture in a
single MCP call instead of orchestrating a dozen tools (and silently skipping
some). Each section is fault-tolerant — a failed one is noted in `errors`,
never sinks the brief.

Routing by asset class:
  * equity/etf → fundamental+macro conviction (brain) + day-trade setup (signals)
  * crypto/fx  → technical setup (market_setup) + momentum/macro/vol/USD (brain)
  * futures    → analysis brief (macro/COT/price/term/news) + COT positioning
Plus, when the symbol is tracked in the registry: realized-vol regime and
symbol-tagged news. Sections that were not attempted or returned empty are
listed in `skipped` (with a reason) so agents do not confuse omission with a
silent success. Failures that raise still land in `errors`. A shared macro regime
read frames everything.

Pure composition over existing services — no new provider logic. Research
context, never a trade trigger.
"""

from __future__ import annotations

from typing import Any

from services import analysis
from services import instruments as reg

DISCLAIMER = (
    "Composed research package (conviction + setup + positioning + vol + news + "
    "macro) — research only, never a trade trigger or order."
)


_REGISTRY_SKIP = "not in registry — add via Registry UI or instruments_add"


def _skipped_sections(
    asset: str,
    inst: Any,
    sections: dict[str, Any],
    errors: dict[str, str],
) -> dict[str, str] | None:
    """Explain absent optional sections (distinct from `errors` = fetch failed)."""
    skipped: dict[str, str] = {}

    if not inst:
        skipped["volatility"] = _REGISTRY_SKIP
        skipped["news"] = _REGISTRY_SKIP
        if asset in ("crypto", "forex"):
            skipped["conviction"] = f"{_REGISTRY_SKIP} (crypto/forex conviction needs tracked id)"
        elif asset == "futures":
            skipped["brief"] = _REGISTRY_SKIP
            skipped["positioning"] = _REGISTRY_SKIP
    else:
        if "volatility" not in sections and "volatility" not in errors:
            skipped["volatility"] = "volatility data unavailable"
        if "news" not in sections and "news" not in errors:
            skipped["news"] = "no headlines tagged to this symbol"
        if asset == "futures" and "positioning" not in sections and "positioning" not in errors:
            if not getattr(inst, "cot_code", None):
                skipped["positioning"] = "registry instrument has no COT code"
        if asset in ("crypto", "forex") and "conviction" not in sections and "conviction" not in errors:
            skipped["conviction"] = "conviction unavailable"

    return skipped or None


def _infer_asset(symbol: str) -> str:
    s = (symbol or "").upper().strip()
    if s.endswith("=F"):
        return "futures"
    if "-USD" in s or (s.endswith("USD") and "-" in s):
        return "crypto"
    if len(s) == 6 and s.isalpha():
        return "forex"
    return "equity"


def brief(symbol: str, asset: str | None = None) -> dict:
    """One-call research package for a symbol, routed by asset (fault-tolerant)."""
    symbol = (symbol or "").strip()
    if not symbol:
        raise ValueError("symbol is required")

    inst = None
    try:
        inst = reg.resolve(symbol)
    except Exception:  # noqa: BLE001 — not tracked is fine; raw-symbol tools still work
        inst = None
    asset = (asset or (inst.asset if inst else None) or _infer_asset(symbol)).lower().strip()
    if inst is None and asset in ("equity", "etf"):
        try:
            inst = reg.ensure(asset, symbol)
        except Exception:  # noqa: BLE001 — vol/news enrichers are optional
            inst = None

    errors: dict[str, str] = {}

    def grab(name: str, fn):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            errors[name] = f"{type(exc).__name__}: {exc}"[:160]
            return None

    macro_read = grab("macro", analysis.regime) or {}
    macro = {"regime": macro_read.get("regime"), "score": macro_read.get("score")}

    sections: dict[str, Any] = {}

    if asset in ("equity", "etf"):
        from services import brain, signals
        sections["conviction"] = grab("conviction", lambda: brain.verdict(symbol))
        sections["setup"] = grab("setup", lambda: signals.trade_setup(symbol))
    elif asset in ("crypto", "forex"):
        from services import brain_crypto, brain_forex, market_setup
        sections["setup"] = grab("setup", lambda: market_setup.market_setup(asset, symbol))
        if inst:
            verdict = brain_crypto.verdict if asset == "crypto" else brain_forex.verdict
            sections["conviction"] = grab("conviction", lambda: verdict(inst.id))
    elif asset == "futures":
        if inst:
            sections["brief"] = grab("brief", lambda: analysis.brief(inst.id))
            if inst.cot_code:
                from services import cot
                sections["positioning"] = grab("positioning", lambda: cot.positioning(instrument=inst.id))

    # Registry-scoped enrichers (need a tracked id).
    if inst:
        from services import volatility as vol_svc
        sections["volatility"] = grab("volatility", lambda: vol_svc.volatility(inst.id))
        from services import news as news_svc
        feed = grab("news", lambda: news_svc.feed(instrument=inst.id, limit=6))
        headlines = (feed.get("headlines") or [])[:6] if feed else []
        if headlines:
            sections["news"] = headlines

    return {
        "symbol": symbol.upper(),
        "asset": asset,
        "in_registry": inst is not None,
        "macro": macro,
        "synthesis": _synthesize(symbol, asset, sections, macro),
        "sections": sections,
        "skipped": _skipped_sections(asset, inst, sections, errors),
        "errors": errors or None,
        "disclaimer": DISCLAIMER,
    }


def _synthesize(symbol: str, asset: str, sections: dict, macro: dict) -> str:
    """Plain one-liner stitching the headline reads together."""
    bits: list[str] = []
    conv = sections.get("conviction") or {}
    if conv.get("conviction"):
        bits.append(f"conviction {conv['conviction'].upper()}")
    setup = sections.get("setup") or {}
    if setup.get("bias"):
        play = " · in play" if setup.get("in_play") else ""
        bits.append(f"setup {setup['bias'].upper()}{play}")
    pos = sections.get("positioning") or {}
    if pos.get("trend"):
        bits.append(f"COT {pos['trend']}")
    brf = sections.get("brief") or {}
    if not bits and brf.get("read"):
        bits.append(str(brf["read"]))
    regime = macro.get("regime")
    frame = f" into a {regime} macro" if regime else ""
    head = "; ".join(bits) if bits else "limited data"
    return f"{symbol.upper()} ({asset}): {head}{frame}."
