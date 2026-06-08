"""Volatility regime classification — where current vol sits vs its own history.

The research-useful framing: not "vol will be X" but "vol is in the Nth percentile
of its 1-year range → calm / normal / elevated / stressed." Like the COT/regime
reads in the analysis layer, it's interpreted research context, never a trigger.
"""

from __future__ import annotations

import numpy as np


def vol_regime(current: float, history) -> dict:
    """Classify `current` vol against its `history` distribution.

    Returns {"percentile", "regime", "current", "median"}. Percentile is the share
    of history below the current level.
    """
    h = np.asarray(history, dtype=float)
    h = h[~np.isnan(h)]
    if len(h) < 2:
        raise ValueError("need >= 2 history points")
    pct = float(np.mean(h < current) * 100.0)
    if pct >= 90:
        regime = "stressed"
    elif pct >= 70:
        regime = "elevated"
    elif pct >= 30:
        regime = "normal"
    else:
        regime = "calm"
    return {
        "percentile": round(pct, 1),
        "regime": regime,
        "current": float(current),
        "median": float(np.median(h)),
    }
