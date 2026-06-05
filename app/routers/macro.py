"""V1 — Macro Dashboard router (SPEC.md §4 V1).

Exposes the composed macro dashboard as one endpoint. Per SPEC §2/§6 this earns
its place over OpenBB's raw REST because it *merges* multiple sources (rates,
dollar/FX, macro tiles, index levels, calendar) into one cached, normalized
response — it is not a 1:1 passthrough.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import Envelope
from services import macro

router = APIRouter(prefix="/macro", tags=["V1 — Macro Dashboard"])


@router.get("/dashboard", response_model=Envelope)
def macro_dashboard() -> Envelope:
    """Risk-on/off snapshot: rates + 2s10s, dollar/FX, macro tiles, index levels,
    and the (provider-dependent) economic calendar. Each panel is independently
    fault-tolerant; a degraded panel reports `ok=false` without failing the call.
    """
    data = macro.build_dashboard()
    return Envelope(
        data=data,
        provider="mixed (yfinance, fred, federal_reserve, fmp)",
        freshness="research context — EOD/daily; not a tradeable signal",
    )
