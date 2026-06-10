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

from services import analysis, fundamentals

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


def verdict(symbol: str) -> dict:
    """Fuse bottom-up fundamentals + top-down macro into one conviction result."""
    symbol = symbol.upper().strip()
    fund = fundamentals.dashboard(symbol)  # bottom-up (fault-tolerant inside)
    read = fund.get("read") or {}
    labels = read.get("labels") or {}
    flags = list(read.get("flags") or [])
    analyst_upside = (fund.get("analyst") or {}).get("upside")

    try:
        reg = analysis.regime()
    except Exception:  # noqa: BLE001 — macro is one input; degrade without it
        reg = {}
    regime_label = reg.get("regime")

    bottom_up, analyst_pt = _score(labels, analyst_upside)
    macro = _macro_lean(regime_label)
    total = bottom_up + analyst_pt + macro
    conviction = _conviction(total)

    # If we have essentially no fundamental signal, say so rather than implying one.
    has_fundamentals = any(labels.get(k) for k in ("valuation", "quality", "growth"))
    if not has_fundamentals and analyst_upside is None:
        conviction = "insufficient"

    return {
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
        "fundamentals": fund,
        "disclaimer": "Synthesized research conviction (fundamentals + macro) — not advice or a trade trigger.",
    }
