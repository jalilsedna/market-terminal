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
  - **Vibe-Trading** (HKUDS) — a **second** bot, **LIVE** on its own Railway
    project (crypto-only), on a **separate Alpaca paper account** (`PA3RT2L7JKF7`).
    See `docs/vibe-trading.md`.
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
| **Vibe-Trading** | **LIVE on its own Railway project** (fork of `HKUDS/Vibe-Trading`, port 8899, volume `vibe-trading-volume` at `/home/vibe/.vibe-trading`). Brain DeepSeek (`deepseek-v4-pro`), market-terminal MCP wired (`agent.json`), Alpaca **#2 paper** account `PA3RT2L7JKF7` (separate from `alpaca-61b238e3`). End-to-end agent run **SUCCESS** (read account + `analysis_regime`, no orders). |

## Current trading state (paper, OpenAlice / `alpaca-61b238e3`)

- **JNJ 106 sh** — entry $239.18 · **GTC OCO live**: stop **$233.54**, TP **$248.11**.
- **LLY 15 sh** — entry $1,155.51 · **GTC OCO live**: stop **$1,108.00**, TP **$1,194.95**.
- **IBKR** `ibkr-tws-aa6a879b`: flat, $1M paper.
- **Bracket lesson (load-bearing):** these went **naked over the prior weekend** when
  a **MKT DAY** bracket's stop/TP children expired at the 4 PM ET close. **Held
  positions MUST use GTC legs**, and you must **verify on the venue after the close**
  (`getOrders` may show only the parent). See `docs/openalice-multi-broker.md`.

## Recent changes (latest first, on `main`)

- **Vibe-Trading LIVE (A11)** — second bot deployed on its own Railway project:
  DeepSeek brain, market-terminal MCP wired (`agent.json`), Alpaca **#2 paper**
  `PA3RT2L7JKF7`, **crypto-only mandate** set + verified, `alpaca-py` persistence
  baked into the fork image, Web-UI auth/`chown` fixes. End-to-end agent run **SUCCESS**.
- **`ALICE_URL` set** — Execution tab now points at the live cloud OpenAlice.
- **Instruments bulk-prune** endpoint added (`app/routers/instruments.py` + tests).
- **Fallback agent DEFERRED** (operator decision) — see Open item #4.
- **News Pulse analyst** pending Anthropic credits (key valid; rule-based fallback live).
- Earlier: UTA id sync + **A9 DONE** (PR #92), Execution-tab host-agnostic (PR #94),
  Vibe-Trading doc + **A10** contract-map / `decision_brief.execution` / `cpu_avx2` (PR #95).

**Open draft PRs (not merged):** **#93** fallback-agent doc (deferred — see #4);
**#82** old `openalice-use-cursor.sh` Cursor-switch helper (likely obsolete now
that the fallback is deferred + cloud-headless supersedes the Cursor path). Both
are candidates to **merge-doc-only or close**.

## Open items / next

1. ~~**Set `ALICE_URL`** on market-terminal's Railway service~~ ✅ **DONE
   (2026-06-14)** — operator set the variable in Railway; the Execution tab now
   points at the live cloud OpenAlice.
2. **First IBKR paper FX trade** — forex opens **Sun ~22:00 UTC**. Alice proposes a
   EURUSD/USDCHF/XAUUSD card → human approves `placeOrder` (GTC bracket).
3. **Deploy Vibe-Trading (second bot) — ✅ LIVE (2026-06-14).** Own Railway project
   (`vibe-trading`), fork of `HKUDS/Vibe-Trading` (Dockerfile, `python:3.11-slim`,
   binds `0.0.0.0:8899`; no VOLUME/AVX2 issues). One volume `vibe-trading-volume` at
   `/home/vibe/.vibe-trading` (Railway allowed only one; sessions/runs not persisted).
   - **Brain:** `LANGCHAIN_PROVIDER=deepseek`, `DEEPSEEK_API_KEY`,
     `LANGCHAIN_MODEL_NAME=deepseek-v4-pro`, `DEEPSEEK_BASE_URL`, `API_AUTH_KEY`,
     `VIBE_TRADING_TRUST_DOCKER_LOOPBACK=1`. Preflight LLM OK.
   - **Research:** `agent.json` at `/home/vibe/.vibe-trading/agent.json` → market-terminal
     MCP (`streamableHttp`, Bearer `AUTH_TOKEN`).
   - **Broker:** Alpaca **#2 paper** `PA3RT2L7JKF7` (separate from `alpaca-61b238e3`).
     Keys live in `/home/vibe/.vibe-trading/alpaca.json` (`{api_key, secret_key,
     profile:"paper", feed:"iex", readonly:false}`) — **NOT** via env or `connector
     configure` (that CLI is TWS-only). The CLI `connector check`/`account` shows
     "(none)" cosmetically; the **agent path works** (`vibe-trading run -p "…"` read
     the account + `analysis_regime`, SUCCESS, no orders).
   - **Two small follow-ups:**
     - **Persistence:** ✅ DONE — `alpaca-py>=0.40` added to the fork's
       `agent/requirements.txt` and rebuilt; verified `alpaca-py 0.43.4` in the image
       and the agent still reads the account after a fresh redeploy.
     - **Mandate:** ✅ DONE (2026-06-14) — crypto-only coordination mandate written
       to `/home/vibe/.vibe-trading/live/alpaca/mandate.json` (on the volume): universe
       `[crypto]`, caps $100/order · $800 exposure · 5 trades/day · 1.0 leverage,
       account_ref `PA3RT2L7JKF7`, 1yr expiry. `load_mandate('alpaca')` verified.
       Clean split: **OpenAlice = equities + forex/metals, Vibe-Trading = crypto**
       (the fail-closed gate denies VT any non-crypto order). To change the lane,
       rewrite that file (operator-only path; the agent can't write it).
   - **Gotcha recap:** Railway Console = **root** (`HOME=/root`); server = **vibe**
     (`HOME=/home/vibe`). Run connector/config commands with `export HOME=/home/vibe`
     + `chown vibe:vibe`, or they land in `/root` and the server won't see them.
   - **Web UI gotchas (both resolved):** (a) the remote Web UI needs the **`API_AUTH_KEY`**
     value pasted into **Settings → Server API key** — it's a self-chosen secret; set the
     *same* value as the Railway env var (an empty var = nothing for the browser to match).
     (b) Running the CLI **as root** created root-owned `sessions.db` + `memory/` on the
     volume → the `vibe` Web-UI server hit `sqlite3 ... attempt to write a readonly
     database` on `POST /sessions` ("Failed to send message"). Fix: `chown -R vibe:vibe
     /home/vibe/.vibe-trading` + restart. Web UI Agent verified (created a session, ran
     `analysis_regime`). "Connector runtime: no connector connected" in the UI = idle
     live-runner status, **not** an error. A-share symbols (e.g. `000001.SZ`) need
     `TUSHARE_TOKEN` (unset) — expected; use US/crypto/market-terminal-covered names.
4. **Fallback agent (PR #93) — DEFERRED (2026-06-14, operator decision).** A
   subscription cap only degrades **monitoring/new analysis**, not **protection**
   (GTC stops live on the broker's servers). The cron is modest (~12 runs/day), so
   caps are unlikely from it alone. The cloud-first reasoning (why **not** Cursor —
   shell-only, not headless — nor Codex headless — MCP disabled — and to use a
   dedicated **`agent-sdk`** profile instead) lives in **draft PR #93**, which is
   **not merged** (`openalice-cursor-fallback.md` on `main` is still the older
   WSL/interactive version). Revisit only if caps actually bite — then merge #93's
   doc (or close it). Do **not** add the paid-API `agent-sdk` profile for now.
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
