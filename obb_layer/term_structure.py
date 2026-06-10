"""OpenBB + FMP data functions for V5 — Futures Term Structure.

Commodity curves (GC/CL/NG) use FMP ``commodities-list`` + quotes (see
``obb_layer/fmp_curve.py``). VIX uses OpenBB's cboe provider (``VX_EOD``).
"""

from __future__ import annotations

from cache.store import cached
from circuit import guarded
from obb_layer.client import get_obb
from obb_layer.fmp_curve import futures_curve as fmp_futures_curve
from obb_layer.normalize import to_records


@cached("eod")
@guarded()
def futures_curve(symbol: str, provider: str = "fmp", date: str | None = None) -> list[dict]:
    """Forward price curve across expirations for a futures root.

    GC/energy: FMP commodities (root ``GC``, ``CL``, ``NG``).
    VIX: OpenBB cboe (``VX_EOD``). Pass ``date`` (YYYY-MM-DD) for a prior session.
    """
    if provider == "cboe":
        obb = get_obb()
        kwargs: dict = {"symbol": symbol, "provider": provider}
        if date:
            kwargs["date"] = date
        return to_records(obb.derivatives.futures.curve(**kwargs), sort_by_date=False)

    if provider == "fmp":
        return fmp_futures_curve(symbol, date=date)

    raise ValueError(f"unsupported term-structure provider {provider!r}")
