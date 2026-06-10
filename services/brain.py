"""Decision brain (ROADMAP H5) — fuses inputs into a RESULT.

The terminal's views are *inputs* (fundamentals, macro regime, vol, …). This is
the layer that puts them together and produces a single per-ticker **conviction**
verdict — the thing a decision actually rests on, not raw numbers.

v1 fuses the two strongest, cleanly-available axes for an equity:
  * bottom-up — the fundamental `read` (valuation/quality/growth/analyst), and
  * top-down — the macro risk-on/off regime (the environment).
Each contributes a signed score; the sum maps to constructive / neutral /
cautious, with a plain-language summary and risk flags (earnings event-risk,
balance-sheet distress). Fault-tolerant: missing pieces just don't vote.

Research synthesis — never a trade trigger or advice. Pure scoring (`_score`,
`_summarize`) is unit-tested; `verdict()` wires in the data.
"""

from __future__ import annotations

from typing import Any

from services import analysis, fundamentals, instruments

_VAL = {"cheap": 1, "fair": 0, "expensive": -1}
_QUAL = {"strong": 1, "mixed": 0, "weak": -1}
_GROW = {"growing": 1, "flat": 0, "declining": -1}


def _macro_lean(regime_label: str | None) -> int:
    if not regime_label:
        return 0
    if regime_label.startswith("risk-on"):
        return 1
    if regime_label.startswith("risk-off"):
        return -1
    return 0


def _score(labels: dict, analyst_upside: Any) -> tuple[int, int]:
    """(bottom_up, analyst_component) signed contributions from the fundamental read."""
    bottom_up = _VAL.get(labels.get("valuation"), 0) + _QUAL.get(labels.get("quality"), 0) \
        + _GROW.get(labels.get("growth"), 0)
    analyst = 0
    if isinstance(analyst_upside, (int, float)):
        analyst = 1 if analyst_upside > 0.10 else -1 if analyst_upside < -0.10 else 0
    return bottom_up, analyst


def _conviction(total: int) -> str:
    if total >= 3:
        return "constructive"
    if total <= -2:
        return "cautious"
    return "neutral"


def _summarize(symbol: str, conviction: str, labels: dict, read_verdict: str | None,
               regime_label: str | None, flags: list) -> str:
    bottom = read_verdict or "limited fundamentals"
    env = f"a {regime_label} macro backdrop" if regime_label else "an unclear macro backdrop"
    line = f"{conviction.upper()} on {symbol}: {bottom}; into {env}."
    if flags:
        line += " Watch: " + "; ".join(flags) + "."
    return line


def _macro_regime() -> str | None:
    try:
        return (analysis.regime() or {}).get("regime")
    except Exception:  # noqa: BLE001 — macro is one input; degrade without it
        return None


def _build(symbol: str, regime_label: str | None, *, include_fundamentals: bool) -> dict:
    """Core synthesis for one symbol given an already-resolved macro regime.

    Pulled out of `verdict()` so `screen()` can compute the macro regime once and
    reuse it across the whole universe instead of re-deriving it per ticker.
    """
    symbol = symbol.upper().strip()
    fund = fundamentals.dashboard(symbol)  # bottom-up (fault-tolerant inside)
    read = fund.get("read") or {}
    labels = read.get("labels") or {}
    flags = list(read.get("flags") or [])
    analyst_upside = (fund.get("analyst") or {}).get("upside")

    bottom_up, analyst_pt = _score(labels, analyst_upside)
    macro = _macro_lean(regime_label)
    total = bottom_up + analyst_pt + macro
    conviction = _conviction(total)

    # If we have essentially no fundamental signal, say so rather than implying one.
    has_fundamentals = any(labels.get(k) for k in ("valuation", "quality", "growth"))
    if not has_fundamentals and analyst_upside is None:
        conviction = "insufficient"

    out = {
        "symbol": symbol,
        "conviction": conviction,
        "score": total,
        "components": {
            "bottom_up": bottom_up,
            "analyst": analyst_pt,
            "macro": macro,
            "macro_regime": regime_label,
            "fundamental_read": read.get("verdict"),
        },
        "flags": flags,
        "summary": _summarize(symbol, conviction, labels, read.get("verdict"), regime_label, flags),
        "disclaimer": "Synthesized research conviction (fundamentals + macro) — not advice or a trade trigger.",
    }
    if include_fundamentals:
        out["fundamentals"] = fund
    return out


def verdict(symbol: str) -> dict:
    """Fuse bottom-up fundamentals + top-down macro into one conviction result."""
    return _build(symbol, _macro_regime(), include_fundamentals=True)


# Conviction ordering for ranking (best → worst); errors/insufficient sink.
_RANK = {"constructive": 3, "neutral": 2, "cautious": 1, "insufficient": 0, "error": -1}


def screen(symbols: list[str] | None = None, limit: int = 25) -> dict:
    """Rank conviction across a universe.

    With `symbols`, screens exactly those tickers. Without, screens every tracked
    instrument that supports fundamentals (equities/ETFs in the registry). The
    macro regime is computed once and shared. Rows are compact (no nested
    fundamentals payload) — call `verdict()` for the full per-ticker breakdown.
    """
    if symbols:
        tickers = [s.upper().strip() for s in symbols if s and s.strip()]
    else:
        tickers = [
            i.symbol.upper()
            for i in instruments.list_all()
            if i.capabilities().get("fundamentals")
        ]
    # De-dupe while preserving order.
    seen: set[str] = set()
    tickers = [t for t in tickers if not (t in seen or seen.add(t))]

    regime_label = _macro_regime()
    rows: list[dict] = []
    for ticker in tickers:
        try:
            rows.append(_build(ticker, regime_label, include_fundamentals=False))
        except Exception as exc:  # noqa: BLE001 — one bad symbol must not sink the screen
            rows.append({
                "symbol": ticker,
                "conviction": "error",
                "score": None,
                "error": f"{type(exc).__name__}: {exc}"[:160],
            })

    rows.sort(key=lambda r: (_RANK.get(r.get("conviction"), -1), r.get("score") or -99), reverse=True)
    return {
        "regime": regime_label,
        "count": len(rows),
        "universe": "explicit" if symbols else "registry",
        "ranked": rows[: max(1, limit)],
        "disclaimer": "Synthesized research conviction ranking (fundamentals + macro) — not advice or a trade trigger.",
    }
