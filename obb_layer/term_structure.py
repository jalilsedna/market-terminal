"""OpenBB data functions for V5 — Futures Term Structure (SPEC.md §4 V5).

Thin fetch→normalize→cache wrapper over `derivatives.futures.curve`. In this
OpenBB version the curve is served by yfinance (fields: expiration, price),
which covers GC and the liquid energy curves (CL/NG). The VIX term structure
(SPEC's fear gauge) needs the cboe provider, which is not installed — see the
router note.
"""

from __future__ import annotations

from cache.store import cached
from obb_layer.client import get_obb
from obb_layer.normalize import to_records


@cached("eod")
def futures_curve(symbol: str) -> list[dict]:
    """Forward price curve across expirations for a futures root (e.g. 'GC=F')."""
    obb = get_obb()
    return to_records(
        obb.derivatives.futures.curve(symbol=symbol, provider="yfinance"), sort_by_date=False
    )
