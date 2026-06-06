# SPEC.md — Multi-Asset Research Terminal

## 1. Purpose & Non-Goals

A private, single-user research and analytics terminal for discretionary futures
day trading (6E, 6B, GC, NQ, YM). It aggregates macro, market-data, positioning,
fundamentals (of futures underlyings/sectors), and news into a few focused views.

**Non-goals (hard boundaries):**
- **Execution is delegated, not done here.** Order entry, position management,
  and live PnL belong to a separate executor — **OpenAlice** (which pulls this
  terminal's research over MCP, see `docs/openalice.md`), NinjaTrader, or
  MetaTrader. This terminal never places/routes orders, holds broker
  connectivity, or stores trade/transfer-capable keys (read-only data keys
  only). Research flows out to the executor; orders never flow back in.
- **No real-time tick feed.** OpenBB is an EOD / delayed / on-demand data layer.
  Treat every number as research context, not a trade trigger.
- **No fork of OpenBB.** We `pip install openbb` and consume it as a library.
  Custom logic lives in our own repo; we never patch the monorepo.

## 2. Architecture

```
NinjaTrader / MetaTrader   ← execution + live feed (separate, untouched)
        │ (manual, human-in-loop)
        ▼
┌─────────────────────────────────────────────┐
│  research-terminal (private repo)            │
│                                              │
│  app/        FastAPI app, routers, schemas   │
│  services/   thin domain logic per view      │
│  obb_layer/  ONLY place that imports openbb  │
│  cache/      response cache (see §6)         │
│  web/        frontend (phase 2+)             │
└─────────────────────────────────────────────┘
        │ imports
        ▼
   OpenBB Platform (library) ── providers ──▶ external APIs
```

**Principles**
- All OpenBB calls funnel through `obb_layer/`. Views never import `obb` directly.
  This isolates us from OpenBB API churn (it deprecates/renames endpoints between
  minor versions — e.g. the 4.5 FMP provider refactor) and gives one place to
  cache, retry, and normalize.
- OpenBB already auto-generates a full REST API and an MCP server from its routers.
  **Decide deliberately (see §6) whether our FastAPI is a value-add wrapper or
  whether we just consume `openbb-mcp-server` / the built-in REST directly.** Do
  not rebuild what OpenBB's router layer already exposes.
- Stack: Python 3.12, FastAPI, OpenBB Platform. Pin `openbb` and the specific
  provider extensions in a lockfile; OpenBB's surface moves fast.

## 3. Data Sources via OpenBB

OpenBB ships standard extensions: `commodity, crypto, currency, derivatives,
economy, equity, etf, fixedincome, index, news, regulators`, plus analysis
extensions `technical, quantitative, econometrics, charting`. Below is what we
actually use, mapped to our needs. Free providers cover ~80% of this; paid keys
(FMP/Intrinio) only where noted.

| Need | OpenBB endpoint(s) | Providers | Notes / caveats |
|---|---|---|---|
| **Futures price (GC, NQ, YM, ES, NG…)** | `obb.derivatives.futures.historical` | yfinance | Continuation symbols (e.g. `GC=F`, `NQ=F`, `YM=F`). **Daily reliable; intraday is short-window + active-contract only.** EOD context, not signals. |
| **Futures term structure / contango-backwardation** | `obb.derivatives.futures.curve` | cboe (VIX only), yfinance, deribit | Real edge for GC/NG roll context. CBOE = VIX term structure. |
| **Futures reference / instruments / stats** | `obb.derivatives.futures.instruments`, `.info` | deribit (crypto), yfinance | Crypto-heavy; thin for CME metals/index. |
| **FX (EUR, GBP underlying 6E/6B)** | `obb.currency.price.historical`, `.snapshots`, `.reference_rates`, `.search` | yfinance, fmp, ecb | Prefer **spot FX** (EURUSD, GBPUSD) for macro context — cleaner than the CME FX-futures series. |
| **COT positioning (the futures trader's edge)** | `obb.regulators.cftc.cot`, `.cot_search` | cftc | Commitment of Traders. Free, weekly. High-value for 6E/6B/GC/NQ/YM net-positioning. |
| **Macro calendar (FOMC, CPI, NFP, ECB, BoE)** | `obb.economy.calendar` | fmp, tradingeconomics(*), nasdaq | Drives the "what moves my contracts today" view. |
| **Macro indicators / series** | `obb.economy.indicators`, `.cpi`, `.gdp`, `.fred_series`, `.interest_rates`, `.money_measures`, `.survey.*` | fred, bls, econdb, federal-reserve | FRED is the workhorse (free key). DXY, yields, CPI, unemployment, PMIs. |
| **Rates / yield curve (risk-on/off context for NQ/YM)** | `obb.fixedincome.government.yield_curve`, `.treasury_rates`, `obb.fixedincome.rate.*` | federal-reserve, fred | 2s10s, front-end repricing → index futures context. |
| **Indices (^GSPC, ^NDX, ^DJI snapshots & constituents)** | `obb.index.price.historical`, `.constituents`, `obb.equity.market_snapshots` | yfinance, cboe, fmp | Cash-index context behind NQ/YM. |
| **Equity screener (sector rotation, breadth)** | `obb.equity.screener`, `obb.equity.compare.groups` | finviz, fmp, nasdaq | Finviz preset `.ini` files in `~/OpenBBUserData/finviz/presets`. `compare.groups` = sector/industry performance heatmap. |
| **News (world + company/sector)** | `obb.news.world`, `obb.news.company` | benzinga, fmp, biztoc, tiingo | Benzinga best for tradable headlines (needs key); biztoc free. |
| **Commodities (gold spot, energy)** | `obb.commodity.price.*`, `obb.commodity.petroleum_status_report` | fmp, eia | Gold spot vs GC futures basis; EIA for energy. |

(*) `tradingeconomics` requires a paid key; default the calendar to `fmp` or `nasdaq`.

**Provider key strategy:** start 100% on free providers (yfinance, fred, cftc,
bls, econdb, federal-reserve, ecb, biztoc, finviz). Add FMP first if you want
better calendar + fundamentals; add Benzinga only if news latency matters. Keys
go in env/config files — OpenBB Hub is being retired, so don't depend on it.

## 4. Modules / Views

Each view = one FastAPI router + one `services/` module + one `obb_layer/` data
function. Frontend renders later; backend returns clean JSON first.

### V1 — Macro Dashboard
The "is today risk-on or risk-off, and what's on the calendar" screen.
- Today/this-week economic calendar filtered to high-impact US/EZ/UK events
  (`economy.calendar`).
- Rates panel: yield curve + 2s10s, Fed funds / SOFR (`fixedincome`).
- Dollar & cross context: DXY, EURUSD, GBPUSD (`currency`).
- Key macro tiles: CPI, NFP/unemployment, PMI, GDP nowcast (`economy.*` via FRED/BLS).
- Index context: ES/NQ/YM cash-index levels + % change (`index`, `equity.market_snapshots`).

### V2 — Watchlist (your instruments)
Fixed watchlist of 6E, 6B, GC, NQ, YM + their underlyings/proxies.
- Per-instrument: last EOD OHLCV, day/week/month % change, ATR(14)
  (`derivatives.futures.historical` + `technical`).
- Spot/cash proxy alongside each future (EURUSD for 6E, GBPUSD for 6B, ^NDX for NQ,
  ^DJI for YM, gold spot for GC) to sanity-check the futures series.
- Stored config (watchlist symbols + proxy mapping) in a local file/SQLite.

### V3 — News Feed
- Merged world + symbol-tagged news (`news.world`, `news.company`), deduped,
  newest-first, filtered to watchlist + macro keywords.
- Tag each headline with which instrument(s) it plausibly affects.

### V4 — COT / Positioning
The genuinely differentiated view; most retail terminals skip it.
- Weekly CFTC Commitment of Traders for each watchlist contract
  (`regulators.cftc.cot`): commercial vs non-commercial net positioning, % change,
  multi-week trend, extremes vs 1y/3y range.

### V5 — Futures Term Structure
- Curve / contango-backwardation for GC and energy where data exists
  (`derivatives.futures.curve`), plus VIX term structure (CBOE) as a fear gauge.

### V6 — Screener (sector rotation / breadth)
- Finviz preset-driven screener + `compare.groups` sector performance heatmap to
  read rotation behind index futures (`equity.screener`, `equity.compare.groups`).

## 5. Build Order (prioritized)

**Phase 0 — Skeleton & data layer (do first, it de-risks everything)**
1. Repo scaffold: FastAPI app, `obb_layer/`, config, lockfile with pinned `openbb`
   + chosen provider extensions.
2. **Capability spike before any view:** in `obb_layer/`, write a probe script that
   calls each §3 endpoint for your real symbols and records what actually returns
   (data shape, granularity, provider that works, rate limits). This is the
   "check what OpenBB already provides" step — it will kill or reshape some views.
3. One normalized response envelope + an error/empty-data contract for all endpoints.
4. Caching layer (§6) — wire it in now, not later.

**Phase 1 — Highest signal-per-effort views**
5. **V1 Macro Dashboard** (backend JSON). Most decision-relevant for an index/FX
   futures day trader.
6. **V4 COT / Positioning.** Cheap (free cftc data), unique, high value for your
   instruments.
7. **V2 Watchlist.** Ties the terminal to your actual contracts.

**Phase 2 — Supporting views**
8. **V3 News Feed.**
9. **V5 Term Structure.**
10. **V6 Screener / sector rotation.**

**Phase 3 — Surface & polish**
11. Frontend (single-page dashboard consuming the FastAPI JSON).
12. Scheduled pre-cache jobs (warm macro + COT + EOD pulls before your session).
13. Optional: expose via `openbb-mcp-server` so you can query the same data layer
    from an AI client.

Rule: each view ships **backend-complete and cached** before the next starts. No
half-wired views.

## 6. Key Decisions & Risks

- **Wrapper vs. passthrough (decide in Phase 0).** OpenBB already generates a REST
  API and MCP server. Our FastAPI is only justified if it adds: merged multi-source
  views (e.g. future + COT + spot proxy in one call), our caching/normalization, and
  our watchlist logic. If a view is a 1:1 proxy to a single OpenBB endpoint, call
  OpenBB's REST directly and don't wrap it. Avoid rebuilding the router layer.
- **Latency/granularity is the central risk.** yfinance EOD is fine; intraday is
  short-window and unreliable for live use. **Do not** let any view imply
  tradeable intraday signals — that belongs to NinjaTrader/MT. Label data freshness
  explicitly in responses.
- **Provider/endpoint churn.** OpenBB deprecates and refactors across minor releases.
  Mitigation: the `obb_layer/` isolation, pinned versions, and the Phase-0 probe
  script re-run on every OpenBB upgrade as a regression check.
- **Rate limits & caching.** Free providers throttle. Cache by (endpoint, params)
  with per-data-type TTLs: intraday/quote ~minutes, EOD ~daily, COT ~weekly, macro
  series ~daily. This is mandatory infra, not an optimization — build it in Phase 0.
- **Symbol mapping is fragile.** CME contracts ↔ yfinance continuation symbols ↔
  spot proxies must live in one explicit config map, validated by the probe script,
  not scattered string literals.
- **Keys & secrets.** Env/config-file only (Hub is being retired). Keep the repo
  private regardless; never commit keys.
