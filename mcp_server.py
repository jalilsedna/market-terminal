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

from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP

from services import alerts as alerts_svc
from services import analysis as analysis_svc
from services import brain as brain_svc
from services import brain_crypto as brain_crypto_svc
from services import brain_forex as brain_forex_svc
from services import cot as cot_svc
from services import decision_brief as decision_brief_svc
from services import filings as filings_svc
from services import fundamentals as fundamentals_svc
from services import instruments as instruments_svc
from services import macro as macro_svc
from services import market_setup as market_setup_svc
from services import movers as movers_svc
from services import news as news_svc
from services import news_pulse as news_pulse_svc
from services import ownership as ownership_svc
from services import screener as screener_svc
from services import signals as signals_svc
from services import term_structure as ts_svc
from services import tradingview as tv_svc
from services import volatility as vol_svc
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
    """All tracked instruments in the registry: EOD price, 1d/1w/1m % change, ATR
    (futures), vol/regime read. Registry starts empty — add symbols via
    `instruments_add` or the web UI."""
    return _safe(watchlist_svc.watchlist)


@mcp.tool()
def instruments_list() -> dict:
    """List tracked instruments with capability flags (price, vol, COT, news, etc.)."""
    items = [i.to_dict() for i in instruments_svc.list_all()]
    return {"instruments": items, "count": len(items)}


@mcp.tool()
def instruments_add(asset: str, symbol: str, label: str | None = None) -> dict:
    """Add an instrument to the registry. asset: futures|crypto|forex|equity|etf."""
    try:
        return instruments_svc.add(asset, symbol, label).to_dict()
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def instruments_remove(item_id: str) -> dict:
    """Remove a tracked instrument by id (e.g. 'equity:AAPL')."""
    instruments_svc.remove(item_id)
    return {"ok": True, "removed": item_id}


@mcp.tool()
def instruments_search(query: str = "", asset: str = "equity", limit: int = 25) -> dict:
    """Autocomplete symbols for the Registry (equity→Alpaca; forex/crypto/futures→catalog)."""
    from services import symbol_search

    try:
        results = symbol_search.search(asset, query, limit=limit)
        return {"ok": True, "asset": asset, "results": results}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}


@mcp.tool()
def cot_positioning(instrument: str | None = None) -> dict:
    """Weekly CFTC Commitment of Traders positioning. With no argument, returns
    all tracked futures with a COT code; pass an instrument id or code for one.
    Reports non-commercial (large specs) vs commercial (hedgers)
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


@mcp.tool()
def analysis_cot() -> dict:
    """Interpreted COT positioning read across the watchlist: large-spec net vs
    its 1y/3y percentile → crowded long (≥85th) / crowded short (≤15th), weekly
    shift, and a contrarian-at-extremes bias. Research context, not a signal."""
    return _safe(analysis_svc.cot_signals)


@mcp.tool()
def analysis_regime() -> dict:
    """Interpreted risk-on / risk-off macro regime read, voted from the VIX
    curve, sector-leadership breadth, the dollar (1w), and the S&P (1w), with the
    contributing signals and rationale. Research context, not a signal."""
    return _safe(analysis_svc.regime)


@mcp.tool()
def analysis_brief(instrument: str) -> dict:
    """"What's moving this symbol" — per-instrument synthesis (registry id or code)
    of macro regime, COT (futures), price/momentum, term
    structure (where it exists), and tagged news, plus a one-line factual read.
    Research context, not a recommendation."""
    return _safe(analysis_svc.brief, instrument)


@mcp.tool()
def analysis_term_structure(lookback_days: int = 7) -> dict:
    """Term-structure dynamics: detects contango↔backwardation **flips** and
    steepening/deepening across the tracked curves (now vs ~`lookback_days` ago).
    VIX is the reliable read (backwardation = stress). Research context."""
    return _safe(analysis_svc.term_structure_signal, lookback_days)


@mcp.tool()
def volatility(instrument: str | None = None, horizon: int = 5) -> dict:
    """Realized volatility, **regime** (calm/normal/elevated/stressed vs ~3y
    history), and a short-horizon vol forecast for one tracked instrument (by id)
    — or the whole registry if omitted. Forecast is EWMA
    (validated best on daily futures), with HAR-RV alongside. Research context for
    sizing / regime awareness — not a trade trigger."""
    if instrument:
        return _safe(vol_svc.volatility, instrument=instrument, horizon=horizon)
    return _safe(vol_svc.dashboard, horizon=horizon)


@mcp.tool()
def market_movers(top: int = 20) -> dict:
    """Whole-market top **gainers / losers / most-active** US stocks for the
    latest session, scanned across the entire market via the Polygon/Massive
    Grouped Daily endpoint (EOD). Filtered to liquid plain-symbol names. `top`
    caps each list. Requires POLYGON_API_KEY; research context, not a trade
    trigger."""
    return _safe(movers_svc.movers, top_n=top)


@mcp.tool()
def fundamentals(ticker: str) -> dict:
    """Per-stock **fundamentals** (FMP): profile, valuation (P/E, P/S, P/B, EV/EBITDA,
    FCF & div yield), quality (Piotroski, Altman-Z, ROE/ROIC, margins, D/E), growth,
    DCF fair value, analyst target/upside, next earnings, peers. Equities/ETFs only.
    Research context, not advice."""
    return _safe(fundamentals_svc.dashboard, ticker)


@mcp.tool()
def brain_verdict(ticker: str) -> dict:
    """The terminal's **synthesized conviction** for a stock — fuses bottom-up
    fundamentals (valuation/quality/growth/analyst) with the top-down macro regime
    into one verdict (constructive / neutral / cautious / insufficient) + a plain
    summary + risk flags (earnings event-risk, distress). Use this as the
    decision-level read; `fundamentals` for the underlying numbers. Research
    synthesis, never a trade trigger."""
    return _safe(brain_svc.verdict, ticker)


@mcp.tool()
def brain_screen(symbols: str | None = None, limit: int = 25) -> dict:
    """Rank the terminal's **conviction** across a universe. Pass comma-separated
    `symbols` (e.g. 'AAPL,MSFT,NVDA'), or omit to screen every tracked
    fundamentals-capable instrument (equities/ETFs in the registry). Shares one
    macro-regime read; returns compact rows sorted best→worst (constructive →
    cautious). Use `brain_verdict` for one ticker's full breakdown. Research
    synthesis, never a trade trigger."""
    syms = [s for s in (symbols or "").split(",") if s.strip()] or None
    return _safe(brain_svc.screen, symbols=syms, limit=limit)


@mcp.tool()
def crypto_brain_verdict(instrument: str) -> dict:
    """**Crypto conviction** for a tracked symbol — fuses momentum (1w/1m), macro
    regime, vol regime, and USD backdrop into constructive / neutral / cautious.
    Pass a registry id (e.g. 'crypto:BTC-USD'). Research synthesis, not a trade
    trigger."""
    return _safe(brain_crypto_svc.verdict, instrument)


@mcp.tool()
def crypto_brain_screen(symbols: str | None = None, limit: int = 25) -> dict:
    """Rank **crypto conviction** across the registry (or comma-separated refs).
    Research synthesis, not a trade trigger."""
    syms = [s for s in (symbols or "").split(",") if s.strip()] or None
    return _safe(brain_crypto_svc.screen, symbols=syms, limit=limit)


@mcp.tool()
def forex_brain_verdict(instrument: str) -> dict:
    """**Forex conviction** for a tracked pair — fuses pair momentum, macro regime,
    vol regime, and USD moves into constructive / neutral / cautious. Pass a
    registry id (e.g. 'forex:EURUSD'). Research synthesis, not a trade trigger."""
    return _safe(brain_forex_svc.verdict, instrument)


@mcp.tool()
def forex_brain_screen(symbols: str | None = None, limit: int = 25) -> dict:
    """Rank **forex conviction** across the registry (or comma-separated refs).
    Research synthesis, not a trade trigger."""
    syms = [s for s in (symbols or "").split(",") if s.strip()] or None
    return _safe(brain_forex_svc.screen, symbols=syms, limit=limit)


@mcp.tool()
def trade_setup(ticker: str) -> dict:
    """**Daily trade-setup bias** for a stock (FMP) — the day-trader's morning read.
    Fuses trend (price vs 50/200-MA), momentum (RSI/ADX), catalysts (analyst
    rating change, price-target trend, fresh news, earnings proximity), smart
    money (insider buy/sell ratio + senate/house trades), and the macro/fundamental
    context into a single `bias` (long/short/neutral), `score`, `conviction`, and
    `in_play` flag (relative volume). Returns concrete `triggers` and risk `flags`.
    Use it to bias/filter order-flow execution — research context, NOT an
    auto-executed trade signal."""
    return _safe(signals_svc.trade_setup, ticker)


@mcp.tool()
def daily_hitlist(limit: int = 15, min_move_pct: float = 2.0) -> dict:
    """**Today's tradeable names** — a whole-market morning scan. Takes the day's
    biggest movers / most-active US stocks and enriches each with catalyst (analyst
    rating change, earnings proximity) + smart-money (insider flow) signals, then
    ranks them by **confluence** (catalyst agrees with the move) + conviction +
    intensity, each with a `bias` (long/short/neutral). The opportunity finder:
    'what's in play today and which way'. Needs FMP + POLYGON_API_KEY. Research
    context, NOT auto-executed trade signals."""
    return _safe(signals_svc.daily_hitlist, limit=limit, min_move_pct=min_move_pct)


@mcp.tool()
def market_setup(asset: str, symbol: str) -> dict:
    """**Technical setup** for a crypto or FX symbol (the crypto/FX analog of
    `trade_setup`, which is stocks-only). Fuses trend (price vs 50/200-MA),
    momentum (RSI/ADX), and in-play participation (relative volume, 52w range)
    into a `bias` (long/short/neutral) + `score` + `conviction`. `asset` is
    'crypto' or 'forex'; `symbol` like 'BTC-USD' or 'EURUSD'. No catalyst/
    smart-money axes (don't exist for these assets). Research context, NOT a
    trade trigger."""
    return _safe(market_setup_svc.market_setup, asset, symbol)


@mcp.tool()
def market_screen(asset: str, symbols: str | None = None, limit: int = 25) -> dict:
    """Rank **crypto/FX technical setups** across the majors (or a comma-separated
    list). `asset` is 'crypto' or 'forex'. Curated universe only — FMP's bulk
    crypto/FX quotes are Ultimate-tier, so there's no whole-market scan. Research
    context, NOT a trade trigger."""
    syms = [s for s in (symbols or "").split(",") if s.strip()] or None
    return _safe(market_setup_svc.screen, asset, symbols=syms, limit=limit)


@mcp.tool()
def sec_filings(ticker: str, limit: int = 15) -> dict:
    """**Recent SEC filings** for a stock — what just got filed (8-K material
    events, 10-Q/10-K reports, Form 4 insider transactions, 13D/G stakes, …) with
    dates, event flags, and links. The 'what changed on the record' lens. Equities
    only; needs FMP. Research context, not a trade trigger."""
    return _safe(filings_svc.filings, ticker, limit=limit)


@mcp.tool()
def smart_money(ticker: str) -> dict:
    """**Who's buying/selling** a stock — interpreted insider + congressional
    trading. Returns an insider buy/sell `lean` (buying/selling/neutral) with the
    buy ratio + recent-purchase count, net congressional flow, and the recent
    insider and Senate/House transactions. The smart-money lens behind
    `trade_setup`'s scoring, on its own. Equities only; needs FMP. Research
    context, never a trade trigger."""
    return _safe(ownership_svc.ownership, ticker)


@mcp.tool()
def news_pulse(symbol: str, asset: str | None = None) -> dict:
    """**24-hour news pulse** for a symbol — monitors the day's headlines and gives
    a brief summary plus an opinion on which way price may lean **for the current
    trading day only**. Fuses news sentiment + technical bias + macro regime. When
    an Anthropic key is configured it reasons like a markets analyst (prose summary
    + catalysts + caveats); otherwise a deterministic rule-based read. `direction`
    is up/down/neutral with a confidence. Research synthesis, never a forecast or
    trade trigger."""
    return _safe(news_pulse_svc.pulse, symbol, asset)


@mcp.tool()
def decision_brief(symbol: str, asset: str | None = None) -> dict:
    """**The complete research package for one symbol in a single call** — use this
    BEFORE proposing any trade so nothing is missed. Routes by asset class and
    fuses everything the terminal produces:
      • equity/ETF → fundamental+macro **conviction** (brain) + day-trade **setup**
        (trend/momentum/catalyst/smart-money)
      • crypto/forex → technical **setup** + momentum/macro/vol/USD **conviction**
      • futures → macro/COT/price/term-structure **brief** + **COT positioning**
    Plus realized-vol regime, symbol-tagged news, and a **24h news pulse**
    (direction + summary) when the symbol is tracked, all
    framed by the current macro regime, with a one-line `synthesis`. Also returns
    a **`conflict`** classification (aligned / momentum_only / fundamental_conflict
    / news_conflict + caution) — size HARDER against it: a high-caution
    fundamental_conflict (technically bullish but fundamentals negative) is a weak
    momentum-only trade regardless of how high the setup score is. `asset` is
    optional (auto-detected). Each section degrades independently (`errors` =
    fetch failed; `skipped` = not attempted or empty, with a reason). Research
    synthesis, NEVER a trade trigger or order."""
    return _safe(decision_brief_svc.brief, symbol, asset)


@mcp.tool()
def tradingview_signals(limit: int = 50) -> dict:
    """Recent **TradingView** strategy/alert signals received via webhook (ticker,
    action, price, message; newest first). These are your TradingView Pine alerts
    forwarded into the terminal — research context, NOT auto-executed. Empty if no
    webhook secret is configured or none have fired yet."""
    return _safe(tv_svc.signals, limit=limit)


@mcp.tool()
def alerts_status() -> dict:
    """Research alert flags over the recorded daily history (volatility regime /
    percentile per instrument, macro regime). Returns each rule with its current
    triggered state and a `triggered_count` — e.g. to check 'is any tracked
    instrument's vol regime stressed right now?'. Flags are research context, not
    a trade trigger."""
    return _safe(alerts_svc.evaluate)


def main() -> None:
    """Run the MCP server.

    Default transport is stdio (for Claude Desktop / Claude Code, which spawn
    this as a subprocess). Pass `--http` to serve over streamable-HTTP instead,
    so a separate app (e.g. OpenAlice) can pull research over a URL without
    spawning Python. Host/port come from config (default 127.0.0.1:8001, kept
    off the REST API's 8000).
    """
    import logging
    import sys

    for _noisy in ("asyncio",):
        logging.getLogger(_noisy).setLevel(logging.CRITICAL)

    # Warm OpenBB on the main thread before serving: FastMCP runs sync tools in a
    # worker thread, and OpenBB's one-time static-package rebuild installs a
    # signal handler that only works on the main thread (see app/main.py).
    from obb_layer.client import get_obb

    get_obb()

    if "--http" in sys.argv:
        from config import get_settings

        settings = get_settings()
        mcp.settings.host = settings.mcp_host
        mcp.settings.port = settings.mcp_port
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
