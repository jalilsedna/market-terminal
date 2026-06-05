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

# 6. Run the API (auto-reload for development)
uvicorn app.main:app --reload
```

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

## Secrets

All API keys live in `.env`, which is **gitignored and never committed**. Start
on free providers (yfinance, fred, cftc, …) — no keys required. Add paid keys
(FMP, Benzinga, …) only when a view needs them. Do not depend on OpenBB Hub.
