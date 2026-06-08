"""Chart router — TradingView Advanced Chart quick-picks.

The Chart tab embeds TradingView's Advanced Chart widget (its full TA toolset).
TradingView is the chart's **display** data source — every *number* in the rest
of the terminal still comes through `obb_layer`. This endpoint just hands the
frontend the watchlist's TradingView symbols (from the one explicit symbol map,
`obb_layer/symbols.py`) so the quick-pick buttons aren't hard-coded in JS.

Pure (only reads the symbol map), so it's unit-tested in CI.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import Envelope
from obb_layer.symbols import WATCHLIST

router = APIRouter(prefix="/chart", tags=["Chart"])

_FRESHNESS = "TradingView chart (display data) — research only, not a trade trigger"


@router.get("/symbols", response_model=Envelope)
def chart_symbols() -> Envelope:
    """Watchlist instruments mapped to their TradingView symbols (quick-picks)."""
    picks = [
        {"code": i.code, "name": i.name, "tv_symbol": i.tv_symbol}
        for i in WATCHLIST.values()
    ]
    return Envelope(data={"picks": picks}, provider="tradingview", freshness=_FRESHNESS)
