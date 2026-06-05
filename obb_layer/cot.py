"""OpenBB data functions for V4 — COT / Positioning (SPEC.md §4 V4).

Thin fetch→normalize→cache wrappers over the CFTC Commitment of Traders
endpoints, confirmed live by the Phase-0 probe (`obb.cftc.cot` returned ~1,627
weekly rows back to 1995 for gold). Free, weekly data — the genuinely
differentiated view for a futures trader.

No domain logic here; net positioning / trend / extremes are computed in
`services/cot.py`.
"""

from __future__ import annotations

from cache.store import cached
from obb_layer.client import get_obb
from obb_layer.normalize import to_records


@cached("cot")
def cot_history(code: str, futures_only: bool = True) -> list[dict]:
    """Full weekly COT history for a CFTC contract `code` (e.g. '088691').

    Uses the legacy report (commercial vs non-commercial), futures-only by
    default. Cached with the weekly COT TTL. Provider: cftc.
    """
    obb = get_obb()
    obbject = obb.cftc.cot(code=code, provider="cftc", futures_only=futures_only)
    return to_records(obbject)


@cached("cot")
def cot_search(query: str) -> list[dict]:
    """Search CFTC contracts by name → returns code/name/category rows.

    Lets the user discover/verify the contract `code` for an instrument.
    """
    obb = get_obb()
    return to_records(obb.cftc.cot_search(query=query), sort_by_date=False)
