# Handoff note (for AI sessions & operators)

**Last updated: 2026-06-14.** Read this first if you're a new AI session picking up
this project. Canonical guidance is still `CLAUDE.md`; this is the live-state summary.

---

## TL;DR

- **market-terminal** (this repo) = a private, single-user **research** terminal on
  Railway. Research only — it never holds broker/trade keys and never places orders.
- **Execution agents pull research from it over MCP and trade on their own side.**
  Two are in play:
  - **OpenAlice** — 24/7 on its own Railway project; **Alpaca + IBKR paper**.
  - **Vibe-Trading** (HKUDS) — a **second** bot, documented and planned on a
    **separate Alpaca paper account** (deploy pending). See `docs/vibe-trading.md`.
- A human approves every order. The research/execution split is deliberate
  (different risk profiles) — don't merge them, and no broker keys in this repo.

## What's live (2026-06-14)

| Piece | Where / id |
|-------|-----------|
| **market-terminal** | Railway · `https://market-terminal-production-131c.up.railway.app` (+ `/mcp`). Bearer `AUTH_TOKEN` (Railway var). `/health` reports providers + `cpu_avx2`. |
| **OpenAlice** | a **separate** Railway project (OpenAlice app + an `ib-gateway` service). State on a Railway **Volume at `/data`** (state under `/data/data`). |
| **Agent runtime (OpenAlice)** | Claude Code on a **Claude subscription** (`CLAUDE_CODE_OAUTH_TOKEN`), not a paid API key. |
| **Alpaca paper (OpenAlice)** | UTA `alpaca-61b238e3` |
| **IBKR paper (OpenAlice)** | UTA `ibkr-tws-aa6a879b` via headless `ib-gateway-docker`, reached at `ib-gateway.railway.internal:4006` (IPv6 socat) |
| **Persona** | `/data/data/brain/persona.md` — routing by `source`, GTC brackets, conflict gate, human-APPROVE |
| **Autonomy** | cron **"Position monitor"** (every 2h) → Inbox. Conflict-gated. |
| **Vibe-Trading** | **Not deployed yet** — documented in `docs/vibe-trading.md`. Will run on its **own** cloud Docker host, **separate Alpaca paper account** (new login/keys), its own LLM key, pulling market-terminal MCP via `~/.vibe-trading/agent.json`. |

## Current trading state (paper, OpenAlice / `alpaca-61b238e3`)

- **JNJ 106 sh** — entry $239.18 · **GTC OCO live**: stop **$233.54**, TP **$248.11**.
- **LLY 15 sh** — entry $1,155.51 · **GTC OCO live**: stop **$1,108.00**, TP **$1,194.95**.
- **IBKR** `ibkr-tws-aa6a879b`: flat, $1M paper.
- **Bracket lesson (load-bearing):** these went **naked over the prior weekend** when
  a **MKT DAY** bracket's stop/TP children expired at the 4 PM ET close. **Held
  positions MUST use GTC legs**, and you must **verify on the venue after the close**
  (`getOrders` may show only the parent). See `docs/openalice-multi-broker.md`.

## Recent changes since the last handoff (merged to `main`)

- **UTA ids synced** to the Railway deploy across all docs + ROADMAP; **A9 marked
  DONE** (cloud-hosted OpenAlice). (PR #92)
- **Execution · Alice tab** made host-agnostic for the cloud OpenAlice — embeds an
  HTTPS Alice, or shows a "set `ALICE_URL`" card. (PR #94)
- **A10 code** (earlier): `obb_layer/ibkr_symbols.py` research↔IBKR contract map,
  `decision_brief.execution` block + web pill, `ensure_default_book()` +
  `POST /instruments/ensure-book`, `/health cpu_avx2`.
- **A11 — Vibe-Trading second bot** documented (`docs/vibe-trading.md`, ROADMAP A11). (PR #95)
- **Parked (draft, NOT merged):** PR #93 — fallback-agent doc. See "Open items".

## Open items / next

1. ~~**Set `ALICE_URL`** on market-terminal's Railway service~~ ✅ **DONE
   (2026-06-14)** — operator set the variable in Railway; the Execution tab now
   points at the live cloud OpenAlice.
2. **First IBKR paper FX trade** — forex opens **Sun ~22:00 UTC**. Alice proposes a
   EURUSD/USDCHF/XAUUSD card → human approves `placeOrder` (GTC bracket).
3. **Deploy Vibe-Trading** (second bot): create the 2nd Alpaca paper account, cloud
   Docker deploy + `API_AUTH_KEY`, wire `~/.vibe-trading/agent.json` MCP, connect
   Alpaca #2, commit its mandate. Steps in `docs/vibe-trading.md`. **Keep its
   broker account separate from `alpaca-61b238e3`.**
4. **Fallback agent (PR #93) — DEFERRED (2026-06-14, operator decision).** A
   subscription cap only degrades **monitoring/new analysis**, not **protection**
   (GTC stops live on the broker's servers). The cron is modest (~12 runs/day), so
   caps are unlikely from it alone. Kept documented in `openalice-cursor-fallback.md`;
   revisit only if caps actually bite. Do **not** add the paid-API `agent-sdk`
   profile for now.
5. Add `AUTO_RESTART_TIME` (e.g. `02:00 AM`) to the `ib-gateway` service so it
   re-auths through IBKR's daily logout unattended.
6. **Rotate `AUTH_TOKEN`** before any non-paper/go-live (it was exposed during a
   setup session). Update it in market-terminal's Railway vars **and** OpenAlice's
   `/data/home/.claude.json` + workspace `.mcp.json` **and** Vibe-Trading's
   `~/.vibe-trading/agent.json`.
7. **News Pulse analyst (Anthropic) — pending operator billing.** `ANTHROPIC_API_KEY`
   is set and **valid**, but the Anthropic account has **no credits**, so the analyst
   pass 402s and News Pulse silently falls back to **rule-based** (still works). Live
   status is in `GET /doctor` → `"llm"` block. Operator will top up credits; no code
   fix needed. (`NEWS_PULSE_MODEL=claude-haiku-4-5` keeps it cheap.)

## Hard rules (do not violate)

- **market-terminal is research-only.** No broker/trade/withdrawal keys here or in
  its Railway vars. Execution lives in OpenAlice / Vibe-Trading only.
- **Two execution bots never share a broker account.** OpenAlice = `alpaca-61b238e3`
  + IBKR; Vibe-Trading = a *separate* Alpaca paper account. Research (MCP) is the
  only thing they share, and it's read-only.
- **Held positions: GTC stop + TP, never DAY** (DAY legs die at the close).
- **Secrets in `.env` / Railway vars only**, never committed.
- **Paper/testnet only** until a deliberate, documented go-live.
- All OpenBB access funnels through `obb_layer/`.

## Canonical docs

`CLAUDE.md` (guidance) · `SPEC.md` (product) · `ROADMAP.md` (backlog + done-ledger) ·
`docs/openalice.md` (integration boundary) · `docs/openalice-cloud-deploy.md` (Railway
recipe) · `docs/openalice-multi-broker.md` (brokers/UTAs/symbol map + GTC lesson) ·
`docs/openalice-daily-runbook.md` (operator loop) · `docs/openalice-prompts.md`
(monitor/scan/reconcile prompts) · `docs/openalice-cursor-fallback.md` (fallback
agent) · `docs/vibe-trading.md` (second bot).
