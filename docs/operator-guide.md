# Operator's guide

The day-2 runbook for the **deployed** terminal: what's running, where data
lives, how to back it up, how to manage users, and the routine ops (rotate
tokens, redeploy). For first-time setup see `README.md`; for the public deploy
see [`docs/deploy-railway.md`](./deploy-railway.md); for the OpenAlice boundary
see [`docs/openalice.md`](./openalice.md).

> **What this is.** A private, single-purpose **research** terminal (macro,
> market data, COT, term structure, sectors, news, volatility/regime, an
> interpreted analysis layer, and C5 history charts + alerts). It serves a web
> UI, a REST API, and an MCP feed from **one** Railway service behind one auth
> gate. It holds **read-only data keys only** — never broker/trade keys.
> Execution lives in OpenAlice, on your machine.

## 1. The shape of the running system

| Surface | Where | Auth |
|---|---|---|
| Web dashboard | `https://<app>.up.railway.app/` | session cookie (`/login`) |
| REST API + `/docs` | same host | `Authorization: Bearer <AUTH_TOKEN>` |
| MCP feed | `https://<app>.up.railway.app/mcp` | same Bearer token |
| Liveness | `/health` (always open) | none — reports `auth_enabled`, providers, EOD chain |
| Diagnostics | `/doctor` | gated — deep report: provider config, DB/volume state, cache, advisory checks |

One container, one process (single worker — the in-memory cache and the
main-thread OpenBB warm assume it). A background **pre-cache** warms every view
on a timer (`PRECACHE_INTERVAL_MIN`, default 30) and records one daily history
snapshot per series.

## 2. Environment variables that matter

Set in Railway → **Variables** (mirror locally in `.env`, which is gitignored).

| Variable | Purpose | Notes |
|---|---|---|
| `AUTH_TOKEN` | Bearer token for API/MCP clients (Alice) | **required on public deploy**; rotating it = §6 |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | bootstrap admin for `/login` | always works, even with no DB users |
| `SESSION_SECRET` | signs the browser cookie | keep stable, or all sessions log out |
| `DB_PATH` | SQLite file location | **point at the mounted volume** → `/data/terminal.db` (§3) |
| `EOD_PROVIDERS` | equity/ETF provider fallback chain | e.g. `tiingo,polygon,yfinance` (§5) |
| `TIINGO_API_KEY` | sturdier equity/ETF data | pairs with `EOD_PROVIDERS` |
| `POLYGON_API_KEY` | Polygon/Massive data (massive.com = Polygon rebrand) | a `massive.com` key works as-is; in the chain **and** powers the Movers tab (free Grouped Daily); unset → Movers off |
| `REGISTRATION_OPEN` | open `/register` self-signup | default **false** — admin creates users instead |
| `PUBLIC_BASE_URL` | informational (docs / Alice config) | `https://<app>.up.railway.app` |
| `PRECACHE_INTERVAL_MIN` | cache-warm + snapshot cadence | `0` disables the scheduler |
| `FRED_API_KEY` | Macro tiles + Dollar/FX (free key) | unset → those panels degrade |
| `FMP_API_KEY` | economic **calendar** + **world-news** wire + the **Fundamentals** brain (H) | paid; auto-upgrades when set; see `docs/fmp.md` |
| `BENZINGA_API_KEY` / `TIINGO_API_KEY` / … | optional provider keys | **read-only data keys only** |
| `TV_WEBHOOK_SECRET` | enables the TradingView webhook (`/webhook/tradingview`) | unset → webhook off; see `docs/tradingview.md` |

Do **not** set `HOST`/`PORT` — Railway injects `$PORT`. Never put broker /
trade / withdrawal keys here; this service is research-only.

## 3. Where data lives + how to back it up

All persistence is one **SQLite** file (`DB_PATH`). It holds four things:
`watchlist` (your My-Watchlist instruments), `snapshots` (daily vol/regime +
macro-regime history — the C5 charts/alerts data), `users` (DB-created
accounts), and a `kv` store.

**The Railway container filesystem is ephemeral** — without a volume, every
redeploy wipes the DB. So the DB must sit on a **mounted volume**:

1. Railway → service → **Volumes** → attach a volume, mount path `/data`.
2. Set `DB_PATH=/data/terminal.db` in Variables.
3. Redeploy. Verify: create a test user in the **Admin** tab → redeploy →
   confirm the user survives.

**Back it up** (the volume is durable but not versioned). From a Railway shell
on the service:

```bash
# point-in-time copy (safe even while running, thanks to WAL)
sqlite3 /data/terminal.db ".backup /data/terminal-$(date +%F).db"
```

Then download it (Railway shell `cat`/transfer, or a one-off `python -c` over
the API). Losing the DB loses your watchlist, alert rules, DB users, and
accumulated history — **prices are always re-fetchable, history is not.**

## 4. Managing users

Auth is on whenever `AUTH_TOKEN` or `ADMIN_PASSWORD` is set. Two account types:

- **Env admin** — `ADMIN_USERNAME`/`ADMIN_PASSWORD`. The bootstrap account; it
  works even with an empty `users` table. Use it to sign in the first time.
- **DB users** — created in the **Admin tab** (shown only to admins) or via
  `POST /admin/users`. Each has a role (`user`/`admin`) and can be disabled.

Self-service signup (`/register`) is **off** by default (`REGISTRATION_OPEN`);
keep it off for a private terminal and create accounts from the Admin tab.
Passwords are PBKDF2-SHA256 hashed (stdlib) — never stored in the clear.

## 5. Data reliability (provider fallback)

Equity/ETF panels (incl. the 11-ETF Sector Rotation hotspot and custom
equity/ETF instruments) walk the `EOD_PROVIDERS` chain until one returns data,
so a yfinance throttle/401 falls back instead of degrading. Recommended:
`EOD_PROVIDERS=tiingo,yfinance` + a free `TIINGO_API_KEY`.

A fallback chain fails **silently** — a bad key just drops to yfinance. Prove
it's really serving:

```bash
python -m scripts.probe_providers      # hits each provider individually for AAPL
```

Crypto/FX/futures stay on yfinance (provider-specific symbol formats; extending
the chain to them needs a symbol-mapping layer — ROADMAP B-next).

## 6. Routine ops

**Rotate `AUTH_TOKEN`** (API/MCP credential):
1. Generate: `python -c "import secrets; print(secrets.token_hex(32))"`.
2. Railway → Variables → set the new `AUTH_TOKEN` → redeploy.
3. Update Alice's `.mcp.json` `Authorization: Bearer` header to match.
4. Verify: new token → `/macro/dashboard` 200; old token → 401.

**Rotate `SESSION_SECRET`:** same idea, but it logs out all browser sessions
(everyone re-signs-in). Only do it if a secret may be compromised.

**Redeploy:** push to `main` (CI runs lint+tests and an import-smoke job), then
Railway auto-builds. First boot is slow — OpenBB rebuilds its static package
once (healthcheck timeout is 300s).

## 7. Using the terminal day to day

Tabs: **Macro · Focus · Chart · Watchlist · My Watchlist · COT · Term Structure ·
Volatility · Sectors · Movers · News · Analysis · Fundamentals · History ▸ Alerts ·
Execution ▸ Alice · Admin**. Everything is **research context, never a trade
trigger** — data is EOD/delayed/weekly and labelled with freshness.

**Fundamentals** (needs `FMP_API_KEY`): per-ticker bottom-up view — profile,
valuation, quality scores (Piotroski/Altman-Z), growth, peers, segmentation. The
first slice of the FMP "brain" (ROADMAP H); see `docs/fmp.md`.

**Movers** (needs `POLYGON_API_KEY`): whole-market top gainers/losers/most-active
for the latest session, scanned across *every* US stock via the free Polygon/
Massive Grouped Daily endpoint (one call = the whole market). Filtered to liquid
plain-symbol names. EOD.

**Chart:** embeds TradingView's Advanced Chart widget (its full TA toolset) for
interactive candlestick/indicator analysis. Quick-pick buttons map the futures
watchlist to TradingView symbols (from `obb_layer/symbols.py`), and a free-form
box accepts any TradingView symbol (`NASDAQ:AAPL`, `BINANCE:BTCUSDT`, `FX:EURUSD`,
…). The chart's data is **TradingView's** (display only, often delayed); every
*number* elsewhere in the terminal still comes through OpenBB.

**History ▸ Alerts (C5):**
- **Charts** plot the recorded daily snapshots (vol/percentile/score over time +
  a regime color band). They start sparse on a fresh deploy and fill in as the
  pre-cache warmer accrues one point per day.
- **Alerts** are research flags over those snapshots. A rule watches one metric
  of one series — `regime ==/!= <level>` (e.g. `vol:GC regime == stressed`) or
  `vol/percentile/score >/>=/</<= <number>` (e.g. `vol:NQ percentile >= 90`).
  Triggered rules show a red badge on the tab and are exposed over MCP
  (`alerts_status`) so Alice can ask "is any vol regime stressed now?". Flags
  never place or route an order.

## 8. Security posture (the standing rules)

- Repo `.env` is gitignored and holds **read-only data keys only**. Never commit
  it. Broker/trade/withdrawal keys never enter this repo or this deploy.
- The public deploy is **always** auth-gated (`AUTH_TOKEN` + admin creds). The
  MCP feed is behind the same Bearer gate.
- OpenAlice (which holds broker keys) stays on your machine and is never
  deployed publicly. Only paper/testnet keys until a deliberate go-live.
- Don't paste secrets into chat or logs; rotate (§6) if one leaks.

## 9. Troubleshooting

**First stop:** hit `GET /doctor` (signed in) — it reports provider config, the
EOD chain, DB/volume writability + row counts, cache state, and advisory checks,
so most of the table below is answered in one call.

| Symptom | Likely cause / fix |
|---|---|
| Watchlist/alerts/users reset after redeploy | No volume, or `DB_PATH` not on it — §3 |
| `/health` shows `auth_enabled:false` on public | `AUTH_TOKEN`/`ADMIN_PASSWORD` unset — set them |
| API returns 401 with the right-looking token | Railway `AUTH_TOKEN` ≠ client token; re-check both ends |
| A panel shows "unavailable" | Provider throttle/egress block — circuit breaker tripped; try Tiingo (§5) |
| Equity panels flaky | Set `EOD_PROVIDERS=tiingo,yfinance` + key, verify with the probe (§5) |
| Charts empty under History | Not enough days of snapshots yet — they accrue daily |
| First request after deploy hangs ~minutes | OpenBB static-package rebuild on first boot — expected once |
