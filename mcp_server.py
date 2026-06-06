"""MCP server exposing the terminal's research views (Phase 3 — SPEC.md §5 step 13).

Lets an AI client (e.g. Claude Desktop / Claude Code) query the SAME composed,
cached views the REST API serves — macro, watchlist, COT, term structure, sector
rotation, news — over the Model Context Protocol (stdio transport). Each tool
returns the view's normalized dict; failed panels degrade gracefully (and the
circuit breaker keeps a throttled provider from being hammered).

This is our own research layer, not a 1:1 re-export of OpenBB's endpoints
(OpenBB ships its own MCP server for that).

Run:
    python mcp_server.py
"""

from __future__ import annotations

from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from services import cot as cot_svc
from services import macro as macro_svc
from services import news as news_svc
from services import screener as screener_svc
from services import term_structure as ts_svc
from services import watchlist as watchlist_svc

mcp = FastMCP("market-terminal")

# All data is research context (EOD / delayed / weekly), never a trade signal.


def _safe(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> dict:
    """Run a view, returning a degraded {ok:false,...} dict instead of raising.

    Some services raise when every provider call fails (e.g. sector rotation,
    news); the REST layer turns that into an envelope, and here we do the same
    so an MCP client always gets structured data, never a bare tool error.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}


@mcp.tool()
def macro_dashboard() -> dict:
    """Risk-on/off macro snapshot: US Treasury yield curve + 2s10s spread, dollar
    & FX (broad USD index, EURUSD, GBPUSD), macro tiles (unemployment, CPI YoY,
    10Y yield, Fed funds), cash-index levels (S&P/Nasdaq-100/Dow), and the
    economic calendar. EOD/daily research context, not a trade signal."""
    return _safe(macro_svc.build_dashboard)


@mcp.tool()
def watchlist_summary() -> dict:
    """The fixed futures watchlist (6E, 6B, GC, NQ, YM): last EOD OHLCV, 1d/1w/1m
    % change, ATR(14), and each future's spot/cash proxy for a sanity check."""
    return _safe(watchlist_svc.watchlist)


@mcp.tool()
def cot_positioning(instrument: str | None = None) -> dict:
    """Weekly CFTC Commitment of Traders positioning. With no argument, returns
    all watchlist contracts; pass an instrument code ('GC', '6E', '6B', 'NQ',
    'YM') for one. Reports non-commercial (large specs) vs commercial (hedgers)
    net positioning, the latest weekly change, and where current net sits within
    its 1-year and 3-year range."""
    if instrument:
        return _safe(cot_svc.positioning, instrument=instrument)
    return _safe(cot_svc.dashboard)


@mcp.tool()
def cot_search(query: str) -> list[dict]:
    """Search CFTC contract codes by name (e.g. 'gold', 'euro fx') — useful to
    discover or verify the code behind a contract."""
    return cot_svc.search(query)


@mcp.tool()
def term_structure() -> dict:
    """Futures term structure (contango vs backwardation, with front/back spread)
    for GC and energy (CL/NG), plus the VIX curve as a fear gauge — VIX
    backwardation = stress/risk-off, contango = calm/risk-on."""
    return _safe(ts_svc.dashboard)


@mcp.tool()
def sector_rotation() -> dict:
    """Sector rotation / breadth: 1d/1w/1m % change for the 11 S&P sector SPDR
    ETFs, ranked by 1-week performance, with leaders and laggards — the rotation
    read behind the index futures."""
    return _safe(screener_svc.sector_rotation)


@mcp.tool()
def market_news(instrument: str | None = None, limit: int = 40) -> dict:
    """Merged, deduped market news tagged to the watchlist instruments and macro
    themes (newest first). Pass an instrument code to filter to one; `limit`
    caps the number of headlines."""
    return _safe(news_svc.feed, instrument=instrument, limit=limit)


def main() -> None:
    # Warm OpenBB on the main thread before serving: FastMCP runs sync tools in a
    # worker thread, and OpenBB's one-time static-package rebuild installs a
    # signal handler that only works on the main thread (see app/main.py).
    import logging

    for _noisy in ("asyncio", "yfinance"):
        logging.getLogger(_noisy).setLevel(logging.CRITICAL)

    from obb_layer.client import get_obb

    get_obb()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
