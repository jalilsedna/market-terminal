# market-terminal

A **private, single-user multi-asset research terminal** built on
[OpenBB](https://openbb.co) (consumed as a library — never forked). Research and
analytics only: macro, market data, positioning (COT), fundamentals of futures
underlyings, and news. **No execution** — order entry and live PnL stay on
NinjaTrader / MetaTrader.

- **Stack:** Python 3.12 · FastAPI · OpenBB Platform
- **Spec:** see [`SPEC.md`](./SPEC.md)
- **Working rules for contributors/AI:** see [`CLAUDE.md`](./CLAUDE.md)

## Project layout

```
app/         FastAPI app, routers, schemas
services/    thin domain logic per view
obb_layer/   the ONLY place that imports openbb
cache/       response cache (per-data-type TTLs)
web/         frontend (later phase)
config.py    loads keys/settings from .env
```

## Setup & run (Windows)

Requires Python 3.12 installed and available via the `py` launcher.

```powershell
# 1. Clone and enter the repo
git clone <your-private-repo-url> market-terminal
cd market-terminal

# 2. Create a Python 3.12 virtual environment
py -3.12 -m venv .venv

# 3. Activate it (PowerShell)
.\.venv\Scripts\Activate.ps1
#    (or, in cmd.exe:  .\.venv\Scripts\activate.bat)

# 4. Upgrade pip and install dependencies
py -3.12 -m pip install --upgrade pip
pip install -r requirements.txt

# 5. Configure secrets — copy the template and edit (the app boots with NO keys)
copy .env.example .env
#    then open .env and fill in any provider keys you need

# 6. Run the API
uvicorn app.main:app
```

> **Auto-reload note.** Use plain `uvicorn app.main:app` for normal use. Do **not**
> point `--reload` at the whole folder: OpenBB rebuilds its static package inside
> `.venv/` the first time the installed extension set changes, and the default
> reloader watches `.venv/`, so it would reload mid-rebuild in a loop. For dev
> auto-reload, scope it to our source only:
> ```powershell
> uvicorn app.main:app --reload --reload-dir app --reload-dir services --reload-dir obb_layer
> ```

The API is then available at <http://127.0.0.1:8000>. Check it is alive:

```powershell
# Health check (shows which providers have keys configured)
curl http://127.0.0.1:8000/health
```

Interactive API docs: <http://127.0.0.1:8000/docs>

To run the Phase-0 capability probe (see `SPEC.md` §5):

```powershell
python -m obb_layer.probe
```

## MCP server (query the views from an AI client)

`mcp_server.py` exposes the same composed views (macro, watchlist, COT, term
structure, sector rotation, news) as **Model Context Protocol** tools, so an AI
client can pull your research directly. It talks stdio and uses your `.env`
keys.

```powershell
python mcp_server.py     # runs the MCP server over stdio
```

**Claude Desktop** — add to `claude_desktop_config.json` (Settings → Developer →
Edit Config), then restart:

```json
{
  "mcpServers": {
    "market-terminal": {
      "command": "C:\\Users\\<you>\\market-terminal\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\<you>\\market-terminal\\mcp_server.py"]
    }
  }
}
```

**Claude Code** — from the project folder:

```powershell
claude mcp add market-terminal -- .venv\Scripts\python.exe mcp_server.py
```

Tools exposed: `macro_dashboard`, `watchlist_summary`, `cot_positioning`,
`cot_search`, `term_structure`, `sector_rotation`, `market_news`. All return
research context (EOD/delayed/weekly), never trade signals.

## Secrets

All API keys live in `.env`, which is **gitignored and never committed**. Start
on free providers (yfinance, fred, cftc, …) — no keys required. Add paid keys
(FMP, Benzinga, …) only when a view needs them. Do not depend on OpenBB Hub.
