# FMP — the fundamental brain (ROADMAP H)

Goal: bring **100% of Financial Modeling Prep's surface into the terminal** (the
bottom-up "brain"), then expose only the terminal's *interpreted* output to Alice
— never raw FMP. This is the company-level complement to the existing top-down
layers (macro regime, COT, volatility, technical movers).

## Architecture

- **REST, not FMP's MCP.** FMP ships an MCP server, but it's a proxy over the same
  REST endpoints. The terminal consumes **REST** via `obb_layer/fmp.py` so it owns
  caching (Starter is rate-capped), normalization, fault-tolerance, and
  interpretation. Alice gets the brain through *our* MCP in the final phase.
- **One client, full surface.** `obb_layer/fmp.py` is a thin httpx client over the
  `stable` API. Key from `FMP_API_KEY`; **errors are sanitized** (the apikey never
  appears). Endpoint paths are centralized in `_PATHS` (a live 404 is a one-line
  fix). Non-OpenBB provider client in obb_layer — same pattern as `grouped.py`.
- **Fault-tolerant.** Every view fetches each block independently; a tier-gated or
  failed endpoint becomes an `errors` entry, never a broken page.

## FMP capability map (groups)

A. **Company** — profile, executives, market cap, float, peers, employees, M&A.
B. **Statements** — income/balance/cashflow (annual/quarter/TTM/growth/as-reported),
   enterprise values, 10-K reports.
C. **Ratios & metrics** — key-metrics, ratios, financial-scores (Piotroski,
   Altman-Z), owner-earnings, revenue segmentation (geo/product).
D. **Valuation** — DCF (standard/levered/custom with WACC inputs).
E. **Analyst** — estimates, grades (+historical), price-target consensus, ratings.
F. **Calendars** — earnings, dividends, IPOs, splits.
G. **ETF/funds** — holdings, sector/country weighting, exposure, info.
H. **Ownership/alt-data** — insider trades, 13F institutional, congress trades, ESG.
I. **Market/other** — market performance, quote/search, indexes, crypto/forex/
   commodity, economics, news, SEC filings, earnings transcripts, technicals, COT.

## Tier note (Starter)

Starter includes A/B/C/D/F/G/quote. Most of **E (analyst)** is Premium+; **13F**
and likely **congress trades** are Ultimate. The fault-tolerant build shows
"unavailable" for gated endpoints — verify live and decide what's worth upgrading.

## Phased build

- **H0 — client foundation** *(done)*: `obb_layer/fmp.py` (`_get` + cached endpoint
  fns), `fmp_base_url`/`fmp_enabled` config, cache TTLs, key-sanitized errors.
- **H1 — core fundamentals view** *(done)*: `services/fundamentals.py` →
  `GET /fundamentals/{ticker}` → **Fundamentals tab** (profile, valuation, quality
  scores, growth, peers, segmentation). CI-tested (`tests/test_fundamentals.py`).
- **H2 — valuation/analyst/calendars + interpreted READ** *(done)*: DCF, analyst,
  earnings; `_read` verdict on Fundamentals tab. See ROADMAP H2.
- **H3 — ETF holdings + ownership/alt-data** *(open)*: insider, 13F-gated,
  congress, ESG.
- **H4 — market/discovery/macro/news/filings + screener** *(open)*.
- **H5 — terminal BRAIN** *(done)*: `services/brain.py` `verdict` + conviction.
- **H6 — expose to Alice (MCP)** *(done)*: `fundamentals`, `brain_verdict`.
- **H7 — brain SCREEN** *(done)*: `brain_screen` MCP + web panel.
- **H8 — trade-setup signal engine** *(done)*: `services/signals.py` →
  `GET /signals/setup/{ticker}` + the `trade_setup` MCP tool. The day-trader's
  morning bias: fuses **trend** (price vs 50/200-MA), **momentum** (RSI/ADX),
  **catalysts** (analyst rating change via `grades-historical`, price-target trend
  via `price-target-summary`, fresh `news/stock`, earnings proximity), **smart
  money** (insider buy/sell ratio + `senate-trades`/`house-trades`), and the
  bottom-up+macro context (`services/brain`) into a single `bias`
  (long/short/neutral) + `score` + `conviction`, plus an `in_play` participation
  read (relative volume) and concrete `triggers`. Fault-tolerant + tier-gated;
  pure scoring unit-tested (`tests/test_signals.py`). Research context, never an
      auto-executed signal — it biases the order-flow execution (NinjaTrader).
- **H9 — daily hit-list scanner** *(done)*: `services/signals.py:daily_hitlist()` →
  `GET /signals/hitlist` + the `daily_hitlist` MCP tool. The opportunity finder:
  takes the whole-market **movers** feed (Polygon/Massive Grouped Daily) and
  enriches each candidate with catalyst (analyst rating change, earnings proximity)
  + smart-money (insider flow), then ranks by **confluence** (catalyst agrees with
  the day's move) + conviction + intensity — each with a long/short/neutral `bias`.
  Needs FMP + `POLYGON_API_KEY`. Pure ranking/scoring unit-tested. Research context,
  never auto-executed.
- **H10 — decision brief** *(done)*: `decision_brief` MCP — one-call Alice package
  (not raw FMP; composes brain + signals + vol + news). See ROADMAP H10.
- **H11 — crypto/FX market setup** *(done)*: `market_setup` / `market_screen` on
  FMP technicals. See ROADMAP H11.
- **H12 — crypto/FX brain** *(done)*: `crypto_brain_*`, `forex_brain_*` MCP tools.

## Setup

Set `FMP_API_KEY` (Railway → Variables). The Fundamentals tab + `/fundamentals/{ticker}`
light up; the economic calendar (B1) and world-news wire (B2) also unlock (see
`docs/data-providers.md`). Verify a ticker (e.g. `AAPL`) and tell me which blocks
show "unavailable" so we lock the Starter tier-gating + any endpoint path fixes.
