"""Shared helpers for market-brain synthesis (crypto, forex).

Pure scoring utilities — unit-tested without OpenBB/network. Equity brain keeps
its own thresholds in `brain.py`; market brains use fewer inputs so thresholds
differ slightly.
"""

from __future__ import annotations

from typing import Any

DISCLAIMER = (
    "Synthesized research conviction (momentum + macro + vol) — "
    "not advice or a trade trigger."
)

RANK = {"constructive": 3, "neutral": 2, "cautious": 1, "insufficient": 0, "error": -1}


def _num(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def macro_lean(regime_label: str | None) -> int:
    if not regime_label:
        return 0
    if regime_label.startswith("risk-on"):
        return 1
    if regime_label.startswith("risk-off"):
        return -1
    return 0


def market_conviction(total: int) -> str:
    if total >= 2:
        return "constructive"
    if total <= -2:
        return "cautious"
    return "neutral"


def momentum_vote(change_1w_pct: Any, change_1m_pct: Any) -> int:
    c1w, c1m = _num(change_1w_pct), _num(change_1m_pct)
    if c1w is None or c1m is None:
        return 0
    if c1w > 0 and c1m > 0:
        return 1
    if c1w < 0 and c1m < 0:
        return -1
    return 0


def vol_vote(regime: str | None) -> tuple[int, list[str]]:
    flags: list[str] = []
    if regime == "stressed":
        flags.append("stressed vol — sizing caution")
        return -1, flags
    if regime == "elevated":
        flags.append("elevated vol — sizing caution")
    return 0, flags


def usd_headwind_crypto(usd_1w_pct: Any) -> int:
    """Stronger USD tends to pressure USD-denominated crypto."""
    usd = _num(usd_1w_pct)
    if usd is None:
        return 0
    if usd > 0.3:
        return -1
    if usd < -0.3:
        return 1
    return 0


def _normalize_fx_symbol(symbol: str) -> str:
    return (symbol or "").upper().replace("/", "").replace("-", "")


def usd_vote_forex(symbol: str, usd_1w_pct: Any) -> int:
    """USD-strength vote for a spot FX pair (6-letter root, e.g. EURUSD)."""
    usd = _num(usd_1w_pct)
    if usd is None:
        return 0
    sym = _normalize_fx_symbol(symbol)
    if len(sym) < 6:
        return 0
    if sym.startswith("USD"):
        if usd > 0.3:
            return 1
        if usd < -0.3:
            return -1
        return 0
    if sym.endswith("USD"):
        if usd > 0.3:
            return -1
        if usd < -0.3:
            return 1
    return 0


def summarize_market(
    *,
    name: str,
    symbol: str,
    asset: str,
    conviction: str,
    components: dict[str, Any],
    flags: list[str],
) -> str:
    bits: list[str] = []
    mom = components.get("momentum")
    if mom == 1:
        bits.append("momentum aligned up (1w & 1m)")
    elif mom == -1:
        bits.append("momentum aligned down (1w & 1m)")
    if components.get("macro_regime"):
        bits.append(f"macro {components['macro_regime']}")
    vol = components.get("vol")
    if vol == -1:
        bits.append("stressed vol")
    usd = components.get("usd")
    if usd == 1 and asset == "crypto":
        bits.append("weaker USD tailwind")
    elif usd == -1 and asset == "crypto":
        bits.append("stronger USD headwind")
    elif usd == 1 and asset == "forex":
        bits.append("USD strength supports pair")
    elif usd == -1 and asset == "forex":
        bits.append("USD strength pressures pair")
    line = f"{conviction.upper()} on {name} ({symbol}): " + ("; ".join(bits) if bits else "mixed signals") + "."
    if flags:
        line += " Watch: " + "; ".join(flags) + "."
    return line
