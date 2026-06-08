"""History recorder (ROADMAP C2 → C5 groundwork).

Once per day (de-duped in `app.db.record_snapshot_daily`), the pre-cache warmer
calls `record_all()` to snapshot the **derived** signals we can't re-fetch later —
per-instrument volatility/regime and the macro regime — into the SQLite history
table. Price/term-structure are NOT stored (re-fetchable from providers); the
value is the interpreted series over time, which feeds the C5 charts/alerts.

Reads already-warmed services (cache hits) and is fully fault-tolerant.
"""

from __future__ import annotations

import logging

from app import db
from services import analysis as analysis_svc
from services import volatility as vol_svc

logger = logging.getLogger("precache")


def record_all() -> dict:
    """Record one daily snapshot per series; returns {"recorded": n}."""
    recorded = 0

    # Per-instrument vol + regime (futures watchlist + any custom instruments).
    try:
        for code, v in (vol_svc.dashboard().get("instruments") or {}).items():
            if not v.get("ok"):
                continue
            regime = v.get("regime") or {}
            payload = {
                "vol": v.get("current_vol_annualized"),
                "regime": regime.get("regime"),
                "percentile": regime.get("percentile"),
            }
            if db.record_snapshot_daily(f"vol:{code}", payload):
                recorded += 1
    except Exception as exc:  # noqa: BLE001 — never let recording break the warm cycle
        logger.warning("history: vol snapshot failed: %s", exc)

    # Macro risk-on/off regime.
    try:
        reg = analysis_svc.regime()
        if reg.get("regime") and db.record_snapshot_daily(
            "regime:macro", {"regime": reg.get("regime"), "score": reg.get("score")}
        ):
            recorded += 1
    except Exception as exc:  # noqa: BLE001
        logger.warning("history: regime snapshot failed: %s", exc)

    if recorded:
        logger.info("history: recorded %d daily snapshot(s)", recorded)
    return {"recorded": recorded}
