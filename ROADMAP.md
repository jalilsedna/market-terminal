# ROADMAP

Tracked backlog for the terminal. **Shipped** = done and merged; **Open** =
deferred, worked around, or flagged. See `SPEC.md` for the product spec and
`docs/openalice.md` for the execution-agent integration.

## ✅ Shipped
- Phase 0 — scaffold, capability probe (`obb_layer/probe.py`), TTL cache.
- Phase 1 — V1 Macro Dashboard, V2 Watchlist, V4 COT/Positioning.
- Phase 2 — V3 News Feed, V5 Term Structure (VIX), V6 Sector Rotation.
- Phase 3 — single-page frontend, pre-cache warmer, per-call circuit breaker,
  MCP server (`mcp_server.py`), Execution tab framing OpenAlice.
- OpenAlice wired as a separate execution app: embedded in the Execution tab,
  running from source under WSL2, agent spawns and replies.

---

## A. Finish the OpenAlice integration (active thread)
- [x] **A1 — Research feed.** market-terminal's MCP (Windows, `:8001`) reaches
      Alice's agent (WSL) via **WSL2 mirrored networking** (`.wslconfig`
      `networkingMode=mirrored`); the workspace `.mcp.json` adds a
      `market-terminal` streamable-http entry at `http://127.0.0.1:8001/mcp`.
- [x] **A3 — Verify end-to-end.** Alice's agent listed all 11 market-terminal
      tools and called `cot_positioning` + `analysis_regime`, returning the
      interpreted gold-COT read and macro regime (with the disclaimer intact).
- [x] **A2 — Make the feed durable.** The `.mcp.json` injection is per-workspace
      and OpenAlice regenerates that file, so it's wiped on regen / new
      workspaces. `docs/openalice.md` → "Making the feed durable" documents
      adding `market-terminal` to OpenAlice's workspace seed (where it already
      injects its own servers) so every workspace gets it, plus the verified
      `streamable-http` format and a post-regen verification step.
- [x] **A4 — Paper account (Alpaca paper).** OpenAlice has **no** mock broker; the
      safe path is an **Alpaca paper** account (`PK…` keys → `paper-api`, cannot
      place real orders). Connected in the UTA; the full loop ran end-to-end:
      Alice pulled the interpreted COT + regime, staged a small GLD paper long
      (2 sh, <1% NAV, stop $385), human-approved via the Web UI, and Alpaca
      round-tripped it (market orders reject outside hours — expected; limit +
      extended-hours or wait for the open). Boundary intact: no broker keys in
      this repo. See `docs/openalice.md` → "The execution side".
- [x] **A5 — Document the OpenAlice-on-WSL setup** — done in
      `docs/openalice-wsl-setup.md`: WSL2 + Ubuntu, `build-essential` (node-pty),
      `claude` login, the 60s UTA timeout edit (`scripts/guardian/dev.ts`, lives
      only in the OpenAlice clone), mirrored-networking `.wslconfig`, run/verify
      steps, and a troubleshooting table.
- [x] **A5b — Claude limit → Cursor fallback.** `docs/openalice-cursor-fallback.md`
      + `scripts/openalice-claude-or-cursor.sh`: when Claude Code caps, continue
      in Cursor Agent (`agent`) with the same workspace MCP / market-terminal feed;
      persona snippet for `data/brain/persona.md` on the OpenAlice host.
- [ ] **A6 — Resolve Claude Code's `/doctor` "MCP" warning** in the WSL agent.
- [x] **A6b — Operational `/doctor` endpoint** (app self-diagnostic). Auth-gated
      `GET /doctor` reports provider config + the EOD chain, SQLite/volume state
      (path, writability, row counts), cache stats, and advisory checks (auth on,
      sturdy provider in chain, DB on a volume, optional keys). `services/doctor.py`
      + `app/db.stats()` + `cache.store.stats()`, CI-tested (`tests/test_doctor.py`).
- [x] **A7 — Rotated the OpenAlice admin token.** Cleared `data/config/auth.json`
      → regenerated on boot (sessions wiped); verified old→401, new→200. Procedure
      captured in `docs/openalice.md`.
- [x] **A8 — Deployed to Railway** (online access). **Live & verified** at
      `market-terminal-production-131c.up.railway.app`: single service serving web
      UI + REST + MCP (mounted at `/mcp`) under one domain and one **auth gate**
      (`app/auth.py`), with `Dockerfile` / `railway.json` / `/login`. Smoke-tested
      (auth on, anon→401, Bearer→200, MCP handshake). Research-only — OpenAlice /
      broker keys never deployed. (Optional: point `DB_PATH` / `CUSTOM…` at a
      Railway volume for watchlist persistence — see C2.)

## B. Data / provider gaps (documented, still open)
- [x] **B1 — Economic calendar.** `obb_layer.economic_calendar` already requests
      `provider="fmp"`, so a **paid FMP key unlocks the calendar** with no code
      change (free tier 402s → degraded panel). Set `FMP_API_KEY`.
- [x] **B2 — World news.** The News feed now **auto-upgrades to a real world wire**
      (`news.world`) when a news-provider key is set — FMP / Benzinga / Tiingo /
      Intrinio, picked in that priority order (`services/news.py:_world_provider`),
      tagged with macro themes + watchlist instruments, and **falls back to FMP
      per-instrument company news** when no world wire (or the wire errors). No
      config flip — add a key and it switches. CI-tested (`tests/test_news.py`).
- [~] **B3 — GC/CL/NG futures curves (V5).** No source provides a real commodity
      curve on the current stack: FMP only has a single continuous quote per
      commodity (not per-expiry), and Polygon/Massive futures need a paid plan.
      GC/CL/NG are marked **unavailable** (`services/term_structure.py:_UNAVAILABLE`)
      and render a calm note; **VIX (CBOE)** is the working term structure. Wire a
      real futures source (Massive Futures / Databento) to re-enable.
- [~] **B4 — Provider reliability.** Shipped a configurable **EOD provider
      fallback chain** (`EOD_PROVIDERS`, `obb_layer/providers.py`): equity/ETF
      fetchers — incl. the sector-rotation 11-ETF fan-out + custom equity/ETF —
      try each provider until one returns data (`EOD_PROVIDERS=fmp,tiingo,polygon`
      by default). `/health` shows the chain. See `docs/data-providers.md`.
- [x] **B-next — Crypto/FX in the fallback chain.** A per-provider
      **symbol-mapping layer** (`obb_layer/symbol_map.py`) rewrites the canonical
      symbol for each provider (`BTC-USD` → Polygon `X:BTCUSD` / Tiingo `btcusd`;
      `EURUSD` → Polygon `C:EURUSD`), so `crypto_history`/`fx_history` now ride the
      same `eod_with_fallback` chain as equity/ETF (unmapped providers are
      skipped). Pure + CI-tested (`tests/test_symbol_map.py`). Futures use
      direct FMP REST (`obb_layer/fmp_market.py`).

## C. Skeleton → product
- [x] **C1 — Tests + CI.** `tests/` covers the auth gate (session/token/expiry +
      every middleware path), the settings on/off logic, and the FastMCP-into-
      FastAPI mount (anonymous → 401, Bearer → real MCP `initialize` handshake) —
      all lightweight (no OpenBB/network). GitHub Actions (`.github/workflows/ci.yml`)
      runs two jobs: **lint-and-test** (ruff + pytest, fast) and **import-smoke**
      (full OpenBB stack + `import app.main` — so an OpenBB-bump that breaks any
      view's import fails CI). Added `pyproject.toml` (ruff + pytest config) and
      `requirements-dev.txt`; ruff-cleaned the existing tree. (The live Phase-0
      probe stays a manual tool — it needs provider keys + network.)
- [x] **C2 — Persistence.** SQLite layer (`app/db.py` — key/value, watchlist,
      history snapshots), unit-tested. The custom watchlist moved off the
      ephemeral JSON onto SQLite (survives restarts; redeploys on a `DB_PATH`
      volume). The pre-cache warmer now records **one daily snapshot per series**
      (`services/history.py`: per-instrument vol/regime + macro regime), exposed
      via `GET /history` + `/history/{series}` — the time-series groundwork for
      C5. (In-memory TTL cache left as-is; a users table is F2.)
- [x] **C3 — Analysis layer (the edge).** Shipped: COT extremes vs 1y/3y
      percentiles, regime vote, curve-flip detection, per-instrument briefs
      (`services/analysis.py`, the `analysis_*` MCP tools, the Analysis tab).
- [x] **C4 — Cross-view "instrument focus."** A **Focus tab**: pick a watchlist
      instrument → its volatility/regime/forecast card + the full "what's moving
      this contract" brief (regime, COT, term structure, momentum, news) on one
      screen (reuses `/volatility/{code}` + `/analysis/brief`). (Follow-up:
      multi-asset focus for custom instruments — needs price/vol-only layout since
      COT is futures-only.)
- [x] **C5 — Charts + alerts.** A **History ▸ Alerts tab**: inline SVG charts of
      the recorded daily snapshots (vol/regime per instrument + macro regime, off
      `/history/{series}`) and research **alert rules** over them
      (`services/alerts.py`, `/alerts` CRUD, persisted in SQLite). Rules watch a
      metric of a series (regime ==/!=, or vol/percentile/score >/>=/</<=) and
      *flag* — surfaced as a header badge and exposed over MCP (`alerts_status`)
      for Alice. Flags are research context, never a trade trigger. Tested in CI
      (`tests/test_alerts.py`).
- [x] **C5b — Interactive price charts (TradingView).** A **Chart tab** embeds
      TradingView's Advanced Chart widget (full TA toolset) for candlestick/
      indicator analysis. Quick-picks map the futures watchlist to TradingView
      symbols via the one explicit map (`obb_layer/symbols.py` → `tv_symbol`,
      served by `/chart/symbols`); a free-form box accepts any TV symbol. The
      chart is TradingView's *display* data (often delayed); every number
      elsewhere still funnels through OpenBB. Tested in CI (`tests/test_chart.py`).
- [x] **B5 — Whole-market Movers (Grouped Daily).** A **Movers tab** +
      `/screener/movers` + `market_movers` MCP tool: top gainers/losers/most-active
      across **every** US stock for the latest session, from Polygon/Massive's
      **Grouped Daily** endpoint — one *free* call returns the whole market, so
      Movers needs just two (latest + prior day) and reuses `POLYGON_API_KEY`.
      `obb_layer/grouped.py` (httpx REST, lazy) + pure `services/movers.py` compute
      (CI-tested), gated on the key. OpenBB doesn't expose this market-wide route,
      so it's the sanctioned "extend in obb_layer" path. (Massive's S3 Flat Files
      give the same data in bulk but are paid-tier, so we use the free endpoint.)
- [~] **C6 — Dynamic multi-asset watchlist.** Shipped: a **My Watchlist** tab +
      `/custom` CRUD endpoints + a JSON store (`services/custom_store.py`, pure +
      tested) let the user **add/remove arbitrary assets across classes** (futures,
      crypto, forex, equity, ETF), each showing price + change + vol/regime. Added
      equity/ETF `obb_layer` fetchers. Custom instruments also flow into the
      **Volatility** tab (asset-agnostic). **Follow-ups:** thread them into the
      Analysis brief dropdown; persist on Railway via a volume (C2); COT stays
      futures-only (CFTC has no stock/crypto positioning).

## E. Forecasting / quant layer — VOLATILITY (toward a Bloomberg-style terminal)
The missing pillar is *forecasting*. We tested price/direction with
[Kronos](https://github.com/shiyu-coder/Kronos) and **it doesn't work** on our
data (full evidence in `docs/decisions.md` §E): daily futures dead, daily crypto
weak, daily FX a modest/uneven ~55% lean with broken bands, hourly no lift — and
independent research ([Rahimikia 2511.18578](https://arxiv.org/abs/2511.18578))
confirms no open model beats persistence on daily price. **Pivoted to
volatility**, the one proven, defensible win — and it needs no torch/service, so
it ships in-core like the analysis layer. Framed as research context (regime /
sizing), never a trigger.
- [x] **E1 — Evaluate Kronos (price/direction).** Done & negative; chase closed.
      Walk-forward harness (`scripts/eval_kronos.py`, `kronos_layer/`) kept for
      the record / any future re-test.
- [x] **E2 — Volatility core (`vol/`).** Pure-numpy realized-vol estimators
      (close-to-close, Parkinson, Garman-Klass), **HAR-RV** forecast + EWMA &
      persistence baselines, and a vol-**regime** read (percentile vs history).
      Unit-tested on synthetic data — validated in-sandbox, no host loop.
- [x] **E5 — Validated on real data.** `scripts/eval_vol.py` walk-forward on GC:
      **EWMA wins** (QLIKE 1.04 vs HAR 1.16 vs persistence 1.19) — small gaps,
      EWMA best, as the literature predicts for daily vol without intraday RV. So
      EWMA is the shipped forecaster (HAR reported alongside). The regime read is
      the headline and works well (GC flagged elevated/stressed correctly).
- [x] **E3 — Wired in.** `services/volatility.py` (composes `vol/` + `obb_layer`
      OHLCV over ~3y) → `/volatility` + `/volatility/{instrument}` router + a
      `volatility` MCP tool (12th tool — Alice gets vol/regime for sizing).
      Forecaster EWMA, HAR alongside, regime classification, one-line read +
      disclaimer.
- [x] **E4 — Visualize.** A **Volatility tab** in the web UI: realized vol,
      regime (calm/normal/elevated/stressed, colour-coded), 1y/3y percentile, and
      the EWMA forecast (HAR faint) per watchlist instrument + the one-line reads.
      Added to the pre-cache warmer so the tab loads warm. (Optional follow-up:
      fold the regime line into `analysis_brief` / the C4 instrument-focus screen.)

## F. Accounts & multi-user (builds on the A8 auth `Users` seam)
The A8 auth layer (`app/auth.py`) was deliberately shaped around a `Users`
abstraction — single admin-from-env today, swappable for a real store without
touching the middleware. These items realize that, toward a product others can
sign into.
- [x] **F1 — Logout button + session UX.** Header session bar ("signed in as X ·
      Sign out") backed by a `current_user` helper + `/whoami` endpoint; shows
      only on an auth-enabled deploy (keyless local dev is unchanged). The SPA
      already redirects to `/login` on a 401, so expiry is handled.
- [x] **F2 — User management + registration.** The `Users` seam is now
      SQLite-backed (C2 `users` table) with PBKDF2 password hashing (stdlib, no new
      deps); the env admin stays as a bootstrap login. **Self-service `/register`**
      (behind `REGISTRATION_OPEN`, default off) and an admin-only **Admin tab** /
      `/admin/users` API to create / list / enable-disable accounts (roles
      admin|user). `/whoami` returns the role; the Admin tab shows only to admins.
      (Follow-up: per-user API/MCP scopes; password reset.)

## D. Housekeeping
- [x] **D1 — `CLAUDE.md` ↔ Claude Project sync.** Refreshed the project-layout +
      conventions to match today's modules, and added a "Keeping this in sync"
      note marking CLAUDE.md canonical (mirror into the claude.ai Project
      instructions on change).
- [x] **D2 — Rotated `AUTH_TOKEN`** (shared in chat during setup); Railway env +
      Alice's `.mcp.json` updated to match (verified new→200, old→401).

## G. Product plan (next phase — agreed roadmap)
- [~] **G1 — FMP integration.** *(this PR)* Paid FMP key unlocks the economic
      **calendar** (B1) and a real **world-news wire** (B2, auto-detected provider
      chain). Follow-ups: surface FMP **fundamentals / ETF holdings / earnings** as
      terminal panels + MCP tools (fills the EEM-holdings gap Alice hit).
- [x] **G2 — UI/UX design pass.** *(shipped)* `web/styles.css` refactored into a
      documented **semantic token system** (surfaces, text, direction green/red/
      amber + soft tints, vol-regime/risk tokens, radius/shadow scale). Polish:
      **tabular-nums** for aligned figures, tinted pills, zebra + accent-hover
      tables, gradient tiles/top-bar, refined panels/tabs/buttons, focus-visible
      states, custom scrollbars, view fade-in. **No HTML/JS change** — every class
      name preserved, so it's a pure visual refresh. (Follow-up: align the
      login/register pages to the same tokens.)
- [~] **G3 — TradingView integration.** *(a) shipped:* `POST /webhook/tradingview`
      ingests TradingView alert/strategy webhooks (secret-gated via `TV_WEBHOOK_SECRET`
      since TV can't send a Bearer header — it's the only open route besides
      `/health`, store-only), persists to SQLite, surfaces in the **Chart tab**
      ("TradingView Signals" panel) and over MCP (`tradingview_signals`) so Alice
      sees them. Research-only — never auto-executed. `services/tradingview.py` +
      `docs/tradingview.md`, CI-tested (`tests/test_tradingview.py`).
      *(b) pending:* manual **Pine→Python** ports of chosen strategies into a
      `signals/` module. *(TradingView has no API to auto-read saved Pine scripts —
      webhooks + manual ports are the real paths.)*
- [ ] **G4 — Provider depth (budgeted).** Add Tiingo-paid (news/intraday) and/or
      Polygon-paid (intraday/real-time + full flat files) as needs arise; Benzinga
      only if low-latency news becomes critical. See `docs/data-providers.md`.

## H. FMP fundamental brain (100% of FMP → terminal, THEN Alice)
Full FMP surface into the terminal brain first; Alice gets only the interpreted
output, last. Consumed via REST (`obb_layer/fmp.py`), not FMP's MCP. See
`docs/fmp.md`. Built fault-tolerant; Starter gates analyst (E)/13F (H).
- [x] **H0 — Client foundation.** `obb_layer/fmp.py` (`_get` + cached endpoint fns,
      key-sanitized errors, centralized paths), `fmp_base_url`/`fmp_enabled`, cache
      TTLs (profile/fundamentals/estimates/calendar).
- [x] **H1 — Core fundamentals view.** `services/fundamentals.py` →
      `GET /fundamentals/{ticker}` → **Fundamentals tab**: profile, valuation
      (P/E, P/S, P/B, EV/EBITDA, div & FCF yield), quality (Piotroski, Altman-Z,
      ROE/ROIC, margins, D/E), growth, peers, revenue segmentation. Defensive field
      extraction; CI-tested (`tests/test_fundamentals.py`).
- [x] **H2 — Valuation/analyst/calendars + interpreted READ.** Added DCF fair
      value (+gap vs price), analyst price-target consensus (+implied upside) &
      rating, and next-earnings date (+days away, last surprise). The
      **`_read` verdict** synthesizes valuation (cheap/fair/expensive from DCF gap)
      · quality (Piotroski/Altman-Z) · growth · analyst upside · earnings proximity
      into one line + flags (event-risk, distress), shown atop the Fundamentals
      tab. CI-tested. (Analyst/DCF may be Starter-gated → degrade.)
      *(H2.1 tuning: valuation label is now driven by **relative** valuation —
      current P/E vs the stock's own 5y median — with DCF kept as context, so
      premium compounders aren't perma-flagged "expensive" by a naive DCF.)*
- [ ] **H3 — ETF holdings + ownership/alt-data** (holdings/sector/country, insider,
      13F [gated], congress trades, ESG).
- [ ] **H4 — Market/discovery/macro/news/filings** + a fundamental **screener**.
- [x] **H5 — Terminal BRAIN.** `services/brain.py` `verdict(ticker)` fuses bottom-up
      (the fundamental read: valuation/quality/growth/analyst) with top-down (macro
      regime) into ONE **conviction** result — constructive / neutral / cautious /
      insufficient — with a plain summary, signed component scores, and risk flags.
      `GET /brain/{ticker}`; the **Fundamentals tab now leads with this Decision
      card** (result, not just data). Fault-tolerant; CI-tested (`tests/test_brain.py`).
      *(Follow-ups: fold in vol/COT for futures-proxy tickers; richer ranking once
      H3/H4 data lands.)*
- [x] **H6 — Exposed to Alice (MCP).** Brought forward at the operator's request to
      test impact on Alice: `fundamentals` + `brain_verdict` MCP tools. Alice now
      gets the terminal's *interpreted* fundamentals + conviction (still research-
      only, never auto-executed). *(H3/H4 raw-data phases can backfill later to
      enrich the brain.)*
- [x] **H7 — Brain SCREEN.** `brain.screen(symbols=None)` ranks **conviction across a
      universe** — explicit tickers or the registry's fundamentals-capable
      instruments (equities/ETFs) — computing the macro regime once and reusing it.
      `GET /brain/screen` (registered before `/{ticker}`), `brain_screen` MCP tool,
      and a **Brain Screen** panel on the Stock Brain tab. Compact ranked rows
      (best→worst); errors sink. Fault-tolerant; CI-tested. Rebuilt on the unified
      registry (replaces the earlier hardcoded-universe draft).
- [x] **H8 — Trade-setup signal engine.** `services/signals.py` `trade_setup(ticker)`
      → `GET /signals/setup/{ticker}` + the `trade_setup` MCP tool. The day-trader's
      daily bias: fuses **trend** (price vs 50/200-MA), **momentum** (RSI/ADX),
      **catalysts** (analyst rating change `grades-historical`, price-target trend
      `price-target-summary`, fresh `news/stock`, earnings proximity), **smart money**
      (insider buy/sell ratio + `senate-trades`/`house-trades`), and the bottom-up+
      macro context (`brain`) → one `bias` (long/short/neutral) + `score` +
      `conviction`, plus an `in_play` relative-volume read and concrete `triggers`.
      New FMP endpoints in `obb_layer/fmp.py` (quote/grades/PT-summary/insider/
      congress/technicals). Fault-tolerant + tier-gated; pure scoring CI-tested
      (`tests/test_signals.py`). Research context, never auto-executed — it biases
      the order-flow execution (NinjaTrader). *(Next: `daily_hitlist` market-wide
      scanner that attaches these signals to today's movers.)*

---

**Status (current):** Deployed + authenticated on Railway (A8) with logout/session
(F1). Research→reason→paper-execute loop proven (A1–A5). Shipped: analysis edge
(C3), the **volatility forecasting pillar** (E1–E5 — Kronos price-forecasting
evaluated and rejected; pivoted to HAR/EWMA + regime, in the API/MCP/UI),
instrument **Focus** screen (C4), the **unified instrument registry** (multi-asset
universe — futures/crypto/forex/equity/ETF, capability-aware; default-seeded with
the 5 reference futures on first boot), provider **fallback** for equity/ETF (B4),
tests + CI green (C1), and a **SQLite persistence** foundation (C2).

**Still open:** **B3** (commodity curves — needs a futures-curve source) · the
**G-series product plan** (FMP fundamentals panels, UI/UX pass, TradingView
webhooks, budgeted provider depth) · minor housekeeping (A6 Claude-Code CLI
warning, C6 brief-threading). **B1/B2 now unlock with an FMP key.**

**Done since:** **C2 history** (`/history`) → **C5 charts + alerts** (History ▸
Alerts tab, `services/alerts.py`, `/alerts`, `alerts_status` MCP tool) and **F2**
(multi-user), plus **C5b** (TradingView Chart), **B5** (whole-market Movers via
Grouped Daily), the **Polygon/Massive** provider, and **B-next** (crypto/FX in
the fallback chain). The core feature set is complete; what remains is paid-data
depth (B1/B2/B3) and housekeeping.
