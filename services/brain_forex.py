"""Forex brain — pair momentum + macro + vol + USD backdrop.

Composes watchlist metrics, macro regime, vol read, and broad USD moves.
Research synthesis only — not a carry-trade or directional trade signal.
"""

from __future__ import annotations

from typing import Any

from services import analysis
from services import instruments as reg
from services import macro as macro_svc
from services import volatility as vol_svc
from services import watchlist as wl_svc
from services.brain_common import (
    DISCLAIMER,
    RANK,
    macro_lean,
    market_conviction,
    momentum_vote,
    summarize_market,
    usd_vote_forex,
    vol_vote,
)


def _macro_regime() -> str | None:
    try:
        return (analysis.regime() or {}).get("regime")
    except Exception:  # noqa: BLE001
        return None


def _usd_1w() -> float | None:
    try:
        dash = macro_svc.build_dashboard()
        fx = dash.get("dollar_fx", {})
        if not fx.get("ok", True) and fx.get("error"):
            return None
        return (fx.get("dollar_index") or {}).get("change_1w_pct")
    except Exception:  # noqa: BLE001
        return None


def _build(inst: reg.TrackedInstrument, regime_label: str | None, *, include_context: bool) -> dict:
    if inst.asset != "forex":
        raise ValueError(f"{inst.id!r} is not forex")

    price: dict[str, Any] = {}
    vol_block: dict[str, Any] = {}
    flags: list[str] = []

    try:
        row = wl_svc.instrument_summary(inst.id)
        if row.get("ok") is False:
            raise ValueError(row.get("error") or "no price data")
        price = {
            "last": row.get("last"),
            "change_1d_pct": row.get("change_1d_pct"),
            "change_1w_pct": row.get("change_1w_pct"),
            "change_1m_pct": row.get("change_1m_pct"),
            "vol_annualized": row.get("vol_annualized"),
            "regime": row.get("regime"),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "id": inst.id,
            "symbol": inst.symbol,
            "asset": inst.asset,
            "name": inst.label,
            "conviction": "insufficient",
            "score": None,
            "error": f"{type(exc).__name__}: {exc}"[:160],
            "disclaimer": DISCLAIMER,
        }

    regime = price.get("regime")
    try:
        vol_block = vol_svc.volatility(inst.id)
        if vol_block.get("ok"):
            regime = (vol_block.get("regime") or {}).get("regime") or regime
    except Exception:  # noqa: BLE001
        pass

    mom = momentum_vote(price.get("change_1w_pct"), price.get("change_1m_pct"))
    macro = macro_lean(regime_label)
    vol_score, vol_flags = vol_vote(regime)
    usd = usd_vote_forex(inst.symbol, _usd_1w())
    flags.extend(vol_flags)

    total = mom + macro + vol_score + usd
    conviction = market_conviction(total)

    components = {
        "momentum": mom,
        "macro": macro,
        "vol": vol_score,
        "usd": usd,
        "macro_regime": regime_label,
    }

    out: dict[str, Any] = {
        "id": inst.id,
        "symbol": inst.symbol,
        "asset": inst.asset,
        "name": inst.label,
        "conviction": conviction,
        "score": total,
        "components": components,
        "flags": flags,
        "summary": summarize_market(
            name=inst.label,
            symbol=inst.symbol,
            asset="forex",
            conviction=conviction,
            components=components,
            flags=flags,
        ),
        "disclaimer": DISCLAIMER,
    }
    if include_context:
        out["price"] = price
        if vol_block:
            out["volatility"] = vol_block
    return out


def verdict(instrument: str) -> dict:
    """Fused forex conviction for one tracked pair."""
    inst = reg.resolve(instrument)
    return _build(inst, _macro_regime(), include_context=True)


def screen(symbols: list[str] | None = None, limit: int = 25) -> dict:
    """Rank conviction across forex registry (or explicit pairs)."""
    if symbols:
        tickers = []
        for ref in symbols:
            inst = reg.resolve(ref.strip())
            if inst.asset != "forex":
                raise ValueError(f"{ref!r} is not forex")
            tickers.append(inst)
    else:
        tickers = [i for i in reg.list_all() if i.asset == "forex"]

    regime_label = _macro_regime()
    rows: list[dict] = []
    for inst in tickers:
        try:
            row = _build(inst, regime_label, include_context=False)
            if row.get("conviction") == "insufficient" and row.get("error"):
                row["conviction"] = "error"
            rows.append(row)
        except Exception as exc:  # noqa: BLE001
            rows.append({
                "id": inst.id,
                "symbol": inst.symbol,
                "conviction": "error",
                "score": None,
                "error": f"{type(exc).__name__}: {exc}"[:160],
            })

    rows.sort(key=lambda r: (RANK.get(r.get("conviction"), -1), r.get("score") or -99), reverse=True)
    return {
        "asset": "forex",
        "regime": regime_label,
        "count": len(rows),
        "universe": "explicit" if symbols else "registry",
        "ranked": rows[: max(1, limit)],
        "disclaimer": DISCLAIMER,
    }
