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
- [~] **B4 — Provider reliability.** Shipped a configurable **EOD provider
      fallback chain** (`EOD_PROVIDERS`, `obb_layer/providers.py`): equity/ETF
      fetchers — incl. the sector-rotation 11-ETF fan-out + custom equity/ETF —
      try each provider until one returns data, so a yfinance throttle falls back
      (add a free Tiingo key + `EOD_PROVIDERS=tiingo,yfinance`). Safe-by-default
      (chain = yfinance, unchanged); `/health` shows the chain. See
      `docs/data-providers.md`. **Follow-up:** a per-provider symbol-mapping layer
      to extend the chain to crypto/FX/futures (different symbol formats).

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
