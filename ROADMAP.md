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
- [ ] **A6 — Resolve Claude Code's `/doctor` "MCP" warning** in the WSL agent.
- [ ] **A7 — Rotate the OpenAlice admin token.**
- [~] **A8 — Deploy market-terminal to Railway** (online access). **Code +
      infra shipped** (`docs/deploy-railway.md`): single service serving web UI +
      REST + MCP (mounted at `/mcp`) under one domain and one **auth gate**
      (`app/auth.py` — login-page session cookie for the browser + Bearer token
      for Alice/MCP/API, on a `Users` abstraction ready for a future DB store +
      registration). Added `Dockerfile`, `railway.json`, `.dockerignore`, the
      `/login` page, and the FastMCP-into-FastAPI mount (validated end-to-end:
      mount + bearer 401→200 + MCP handshake + DNS-rebind config). **Remaining
      (your click-ops):** create the Railway project, set the secrets/env, expose
      a domain, run the smoke test, then point Alice's `.mcp.json` at the public
      `/mcp` URL with the Bearer header. Research-only — **never** deploy
      OpenAlice / broker keys publicly.

## B. Data / provider gaps (documented, still open)
- [ ] **B1 — Economic calendar.** Paywalled on FMP free tier; V1's calendar
      panel is degraded. Needs a paid provider or alternative source.
- [ ] **B2 — World news.** FMP free is paywalled; worked around with
      per-instrument yfinance. Functional but not true world news.
- [ ] **B3 — GC/CL/NG futures curves (V5).** yfinance 401s; only VIX works.
      Needs another source for commodity term structure.
- [ ] **B4 — Provider reliability.** yfinance throttles/401s often; evaluate a
      sturdier EOD provider for the whole terminal.

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
- [ ] **C2 — Persistence.** Cache is in-memory and resets on restart; add a
      disk/SQLite layer + history.
- [x] **C3 — Analysis layer (the edge).** Shipped: COT extremes vs 1y/3y
      percentiles, regime vote, curve-flip detection, per-instrument briefs
      (`services/analysis.py`, the `analysis_*` MCP tools, the Analysis tab).
- [ ] **C4 — Cross-view "instrument focus."** One symbol → its COT + price +
      term structure + news (and later its Kronos forecast — E3) on one screen.
- [ ] **C5 — Interactive frontend.** Editable watchlist, charts, alerts
      (e.g. COT extreme / curve flip).
- [ ] **C6 — Dynamic multi-asset watchlist.** Today the watchlist is a fixed
      5-instrument map hardcoded in `obb_layer/symbols.py` (futures only). Let the
      user **add/remove arbitrary assets across classes** — futures, crypto,
      forex, equities, ETFs — as a persisted, editable instrument list (pairs
      with C2 persistence; builds on the new crypto/forex `obb_layer` fetchers),
      surfaced in both the UI and the MCP feed.

## E. Forecasting / quant layer — toward a Bloomberg-style terminal
The terminal *displays* and *interprets* data; the missing pillar is
*forecasting*. [Kronos](https://github.com/shiyu-coder/Kronos) (MIT) is an
open-source foundation model for OHLCV candlesticks — it takes a price history
and emits a **probabilistic forecast** of the next N bars. Framed as research
context with a disclaimer (like the analysis layer), it fits without crossing the
execution boundary: one more input Alice *pulls*, never a trade trigger.
- [~] **E1 — Evaluate.** Walk-forward harness (`scripts/eval_kronos.py` + the
      isolated `kronos_layer/`) scores Kronos-base vs a persistence baseline.
      **Daily futures: FAILED.** **Daily crypto: weak** (BTC coin-flip, ETH
      marginal). **Daily FX: a modest, real directional edge** (~55% avg, 4/6
      majors beat the always-up baseline) — but no level skill and broken bands.
      A GitHub deep-search ([Rahimikia 2511.18578](https://arxiv.org/abs/2511.18578))
      confirms no open model beats persistence on daily price; volatility is the
      one proven win. **Now testing Kronos zero-shot on *hourly* FX** (its native
      cadence; harness has `--interval 1h`) before any fine-tune — fine-tuning
      daily FX was deprioritized (too little data + evidence says it still fails).
      Full evidence + decisions: **`docs/decisions.md`**.
- [ ] **E2 — Isolated `kronos_layer/`** (the ONLY place that imports torch —
      mirrors the `obb_layer` rule): load tokenizer+model once, cache it, expose
      `forecast(ohlcv_df, horizon) -> probabilistic paths`.
- [ ] **E3 — Wire it in.** `services/forecast.py` + `/forecast/{instrument}`
      router + a `forecast` MCP tool; fold the forecast into `analysis_brief` and
      the C4 instrument-focus screen.
- [ ] **E4 — Visualize.** History + forecast cone (median + quantile band) in the
      frontend.
- [ ] **E5 — Deployment decision.** torch + a ~100M model is heavy (image size,
      RAM). Likely run Kronos as a **separate forecasting service** the terminal
      calls (matches the multi-service Railway future), or keep it feature-flagged
      so the core stays lightweight. Decide before wiring E3 to the public deploy.

## F. Accounts & multi-user (builds on the A8 auth `Users` seam)
The A8 auth layer (`app/auth.py`) was deliberately shaped around a `Users`
abstraction — single admin-from-env today, swappable for a real store without
touching the middleware. These items realize that, toward a product others can
sign into.
- [ ] **F1 — Logout button + session UX.** The `/logout` route exists; surface
      it in the web UI (a button + who's logged in), and handle session-expiry
      gracefully (the SPA already redirects to `/login` on 401).
- [ ] **F2 — User management panel.** Replace the single env admin with a
      DB-backed user store (the `Users` seam), an admin panel to create / list /
      disable users, and optional self-service registration. Pairs with C2
      (persistence) for where the user table lives, and gates which API/MCP
      scopes each user gets.

## D. Housekeeping
- [ ] **D1 — Keep `CLAUDE.md` ↔ the Claude Project's custom instructions in
      sync** (rule #1 reframed: execution delegated, not forbidden).
- [ ] **D2 — Rotate `AUTH_TOKEN`** (it was shared in chat during setup); update
      the Railway env and Alice's `.mcp.json` to match.

---

**Status:** Research→reason→paper-execute loop proven (A1–A5); deployed online,
authenticated, on Railway (A8); analysis edge shipped (C3); tests + CI green (C1).
**Next candidates:** **E1** (evaluate Kronos — the forecasting pillar), **C4**
(instrument-focus screen), or **B** (trustworthy data — needed before forecasts
can be trusted; Kronos is only as good as its input bars).
