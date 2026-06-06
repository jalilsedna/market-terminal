"""OpenBB data functions for V5 — Futures Term Structure (SPEC.md §4 V5).

Thin fetch→normalize→cache wrapper over `derivatives.futures.curve`. In this
OpenBB version the curve is served by yfinance (fields: expiration, price),
which covers GC and the liquid energy curves (CL/NG). The VIX term structure
(SPEC's fear gauge) is served by the cboe provider.
"""

from __future__ import annotations

from cache.store import cached
from circuit import guarded
from obb_layer.client import get_obb
from obb_layer.normalize import to_records


@cached("eod")
@guarded()
def futures_curve(symbol: str, provider: str = "yfinance") -> list[dict]:
    """Forward price curve across expirations for a futures root.

    GC/energy use yfinance ('GC=F' etc.); the VIX curve uses cboe ('VIX').
    """
    obb = get_obb()
    return to_records(
        obb.derivatives.futures.curve(symbol=symbol, provider=provider), sort_by_date=False
    )
