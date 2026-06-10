# market-terminal

A **multi-asset research terminal** built on [OpenBB](https://openbb.co)
(consumed as a library — never forked): macro, market data, positioning (COT),
term structure, sector rotation, news, plus an **interpreted analysis layer**
(positioning extremes, risk-on/off regime, per-instrument briefs). It ships a
web dashboard, a REST API, and an **MCP server** so an AI agent can pull the
research directly.

**Research and analytics only — execution is delegated, not duplicated.** No
order entry, position management, or broker connectivity lives here; no
trade/transfer/withdrawal keys ever do. Execution belongs to a *separate* app
([OpenAlice](https://github.com/TraderAlice/OpenAlice)) that **pulls** research
over MCP and decides/executes on its own side. Research flows out; orders never
flow back in. See [`docs/openalice.md`](./docs/openalice.md).

- **Stack:** Python 3.12 · FastAPI · OpenBB Platform · MCP
- **Deploys to:** Railway, as one authenticated service (web + REST + MCP). See
  [`docs/deploy-railway.md`](./docs/deploy-railway.md) to deploy and
  [`docs/operator-guide.md`](./docs/operator-guide.md) for day-2 ops (data,
  backups, users, token rotation).
- **Spec / rules:** [`SPEC.md`](./SPEC.md) · [`CLAUDE.md`](./CLAUDE.md) ·
  backlog in [`ROADMAP.md`](./ROADMAP.md)

## Project layout

```
app/         FastAPI app, routers, schemas, auth, pre-cache
services/    thin domain logic per view (incl. services/analysis.py)
obb_layer/   the ONLY place that imports openbb
cache/       response cache (per-data-type TTLs)
web/         single-page dashboard (vanilla JS) + login page
tests/       pytest suite (auth, config, MCP mount) — CI-gated
docs/        deploy + OpenAlice integration guides
mcp_server.py  exposes the views as MCP tools (stdio or HTTP)
config.py    loads keys/settings from .env
```

## Setup & run (local)

Requires Python 3.12. On Windows use the `py -3.12` launcher; on macOS/Linux use
`python3.12`.

```bash
git clone <your-private-repo-url> market-terminal
cd market-terminal

python3.12 -m venv .venv
source .venv/bin/activate           # Windows: .\.venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env                 # the app boots with NO keys (free providers)
uvicorn app.main:app
```

> **Auto-reload note.** Use plain `uvicorn app.main:app` for normal use. Do **not**
> point `--reload` at the whole folder: OpenBB rebuilds its static package inside
> `.venv/` the first time the installed extension set changes, and the default
> reloader watches `.venv/`, so it would reload mid-rebuild in a loop. For dev
> auto-reload, scope it to our source:
> ```bash
> uvicorn app.main:app --reload --reload-dir app --reload-dir services --reload-dir obb_layer
> ```

The app is then at <http://127.0.0.1:8000> — the dashboard at `/`, interactive
API docs at `/docs`, and a liveness check at `/health` (reports which providers
have keys and whether auth is enabled).

Run the Phase-0 capability probe (re-run after any OpenBB bump — see `SPEC.md`):

```bash
python -m obb_layer.probe
```

## Authentication

Locally with no credentials set, the terminal is **open** (keyless dev). It
becomes **gated** the moment you set credentials — required on any public
deploy:

- `AUTH_TOKEN` — Bearer token for programmatic clients (the MCP feed / API).
- `ADMIN_USERNAME` + `ADMIN_PASSWORD` — the browser `/login` page.
- `SESSION_SECRET` — signs the session cookie (keep stable across restarts).

The browser gets a session cookie; agents/scripts send `Authorization: Bearer
<token>`. `/health` stays open and reports `auth_enabled`. See `app/auth.py` and
[`docs/deploy-railway.md`](./docs/deploy-railway.md).

## MCP server (query the views from an AI client)

`mcp_server.py` exposes the composed views as **Model Context Protocol** tools so
an AI client can pull your research directly.

```bash
python mcp_server.py          # stdio (Claude Desktop / Claude Code spawn it)
python mcp_server.py --http   # streamable-HTTP at http://127.0.0.1:8001/mcp
```

When the app is deployed, the same feed is mounted at `https://<app>/mcp` behind
the Bearer gate — no separate process needed.

**Claude Code** — from the project folder:

```bash
claude mcp add market-terminal -- .venv/bin/python mcp_server.py
```

Tools exposed: `macro_dashboard`, `watchlist_summary`, `cot_positioning`,
`cot_search`, `term_structure`, `sector_rotation`, `market_movers` (whole-market
gainers/losers via Flat Files), `market_news`, `volatility` (realized vol +
regime + forecast), `alerts_status` (C5 research flags), and the
interpreted-signal tools `analysis_cot`, `analysis_regime`, `analysis_brief`,
`analysis_term_structure`, `tradingview_signals` (TradingView alert/strategy
signals received via webhook — see [`docs/tradingview.md`](./docs/tradingview.md)),
and the **fundamental brain** `fundamentals` + `brain_verdict` (per-stock FMP data
+ a synthesized conviction — see [`docs/fmp.md`](./docs/fmp.md)).
All return research context (EOD/delayed/weekly), with a disclaimer — never a
trade trigger.

**Feeding an execution agent (e.g. OpenAlice):** market-terminal stays
research-only and acts as an MCP data source the agent *pulls from*. See
[`docs/openalice.md`](./docs/openalice.md) and
[`docs/openalice-wsl-setup.md`](./docs/openalice-wsl-setup.md).

## Tests

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

CI (`.github/workflows/ci.yml`) runs the same lint + tests on every push/PR, plus
an import-smoke job that installs the full OpenBB stack and imports every view —
so an OpenBB bump can't silently break a panel.

## Secrets

All keys live in `.env`, which is **gitignored and never committed** (only
read-only data-provider keys belong here). Start on free providers (yfinance,
fred, cftc, …) — no keys required. Add paid keys (FMP, Benzinga, …) only when a
view needs them. Do not depend on OpenBB Hub. On Railway, the same variables are
set in the service's environment, never in the repo.
