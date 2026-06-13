# Handoff note (for AI sessions & operators)

**Last updated: 2026-06-13.** Read this first if you're a new AI session picking up
this project. Canonical guidance is still `CLAUDE.md`; this is the live-state summary.

---

## TL;DR

- **market-terminal** (this repo) = a private, single-user **research** terminal on
  Railway. Research only — it never holds broker/trade keys and never places orders.
- **OpenAlice** = the **separate execution agent**. As of 2026-06-13 it runs **24/7
  on its own Railway project**, pulls research from market-terminal over MCP, and
  executes on **Alpaca + IBKR paper**. A human approves every order.
- The split is deliberate (different risk profiles). Don't merge them.

## What's live (2026-06-13)

| Piece | Where / id |
|-------|-----------|
| **market-terminal** | Railway · `https://market-terminal-production-131c.up.railway.app` (+ `/mcp`). Bearer `AUTH_TOKEN` (Railway var). `/health` reports providers + `cpu_avx2`. |
| **OpenAlice** | a **separate** Railway project (single app service built from the OpenAlice Dockerfile + an `ib-gateway` service). State on a Railway **Volume at `/data`** (actual state under `/data/data`). |
| **Agent runtime** | Claude Code on a **Claude subscription** (`CLAUDE_CODE_OAUTH_TOKEN`), not a paid API key. |
| **Alpaca paper** | UTA `alpaca-61b238e3` |
| **IBKR paper** | UTA `ibkr-tws-aa6a879b` via headless `gnzsnz/ib-gateway-docker`, reached at `ib-gateway.railway.internal:4006` (IPv6 socat — see below) |
| **Persona** | `/data/data/brain/persona.md` — routing by `source`, GTC brackets, conflict gate, human-APPROVE |
| **Autonomy** | cron **"Position monitor"** (every 2h) → Inbox. Proven producing real, conflict-gated analysis. |

## How the OpenAlice-on-Railway deploy works

Full validated recipe + gotchas: **`docs/openalice-cloud-deploy.md`** →
"Railway deploy" and "Validated build recipe + gotchas". The non-obvious bits that
cost time:

- **AVX2 is the only hard host requirement** — the `claude` runtime crashes
  `illegal instruction` without it. Two budget VPS masked the CPU ("Common KVM
  processor", no AVX) and were dead ends. Railway/GCP has AVX2 (`/health` →
  `cpu_avx2: true`).
- **Drop the Dockerfile `VOLUME`** line — Railway rejects it (use Railway Volumes).
- `OPENALICE_HOME=/data` → state lands under **`/data/data/`** (double `data`).
- **MCP durability:** market-terminal is registered in the **user-scoped**
  `/data/home/.claude.json` `mcpServers` (every session reads it, survives
  redeploys) — the per-workspace `.mcp.json` template is baked into the image.
- **Tool permissions (headless):** `/data/home/.claude/settings.json` has
  `enableAllProjectMcpServers: true` and a `permissions.allow` list of **read-only**
  tools (`mcp__market-terminal`, `mcp__openalice-workspace`, openalice
  `getPortfolio/getAccount/getMarketClock/listUTAs/getOrders/orderHistory`).
  **`placeOrder` is intentionally NOT allowed** — execution stays human-gated.
- **IB Gateway IPv6 gotcha:** Railway's private net is IPv6; the image's socat is
  IPv4-only. An IPv6 listener is added via a Railway **Custom Start Command**
  (`socat TCP6-LISTEN:4006,fork,reuseaddr TCP4:127.0.0.1:4004 & exec …/run.sh`).
- **One IBKR session per login** — keep any local Gateway OFF or they flap.

## Current trading state (paper)

- **Alpaca** `alpaca-61b238e3`: JNJ 106 sh, LLY 15 sh — both thesis **INTACT** at
  2026-06-13 (constructive, conflict aligned, no stressed-vol).
- **IBKR** `ibkr-tws-aa6a879b`: flat, $1M cash.
- Open monitoring item: verify JNJ/LLY stop/TP legs are **GTC** (orders read tools
  were just granted, so the next monitoring pass covers it).

## Open items / next

1. **Sunday ~22:00 UTC:** first IBKR paper **FX trade** (interactive — Alice
   proposes a EURUSD/XAUUSD trade card, human approves `placeOrder`).
2. Add `AUTO_RESTART_TIME` (e.g. `02:00 AM`) to the `ib-gateway` service so it
   re-auths through IBKR's daily logout unattended.
3. Optional: add an **opportunity-scan** cron (payload in `docs/openalice-prompts.md`).
4. **Rotate `AUTH_TOKEN`** before any non-paper/go-live (it was exposed during a
   setup session). Update it in market-terminal's Railway vars **and** OpenAlice's
   `/data/home/.claude.json` + workspace `.mcp.json`.

## Hard rules (do not violate)

- **market-terminal is research-only.** No broker/trade/withdrawal keys here or in
  its Railway vars. Execution lives in OpenAlice only.
- **Secrets in `.env` / Railway vars only**, never committed.
- **Paper/testnet only** until a deliberate, documented go-live.
- All OpenBB access funnels through `obb_layer/`.

## Canonical docs

`CLAUDE.md` (guidance) · `SPEC.md` (product) · `ROADMAP.md` (backlog + done-ledger) ·
`docs/openalice-cloud-deploy.md` (the Railway recipe) · `docs/openalice-multi-broker.md`
(brokers/UTAs/symbol map) · `docs/openalice-daily-runbook.md` (operator loop) ·
`docs/openalice-prompts.md` (Alice monitor/scan/reconcile prompts).
