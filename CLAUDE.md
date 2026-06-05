# CLAUDE.md

Guidance for Claude (and any AI/automation) working in this repository.

## What this is

A **private, single-user Python research terminal** for multi-asset market
research and analytics. It is built **on top of OpenBB**, which we consume as a
**library** (`pip install openbb`) — never as a fork.

- **Stack:** Python 3.12 · FastAPI · OpenBB Platform
- **Scope:** multi-asset *research* (macro, market data, positioning,
  fundamentals of futures underlyings/sectors, news).
- **Out of scope:** execution. No order entry, no position management, no live
  PnL, no broker connectivity. Execution stays on NinjaTrader / MetaTrader.

See `SPEC.md` for the full product specification.

## Hard rules

1. **Never fork or modify the OpenBB monorepo.** We `pip install openbb` and
   import it as a dependency. All of our own logic lives in *this* repo. If
   OpenBB lacks something, we wrap or extend it here — we do not patch upstream.

2. **Check what OpenBB already provides before building anything new.** OpenBB
   auto-generates a REST API and an MCP server from its routers and ships a
   large catalog of providers/endpoints. Before writing a new module, confirm
   OpenBB doesn't already expose it. Do not rebuild the router layer.

3. **All OpenBB access funnels through `obb_layer/`.** Views and services never
   `import openbb` directly. This isolates us from OpenBB's API churn (it
   deprecates/renames endpoints across minor versions) and gives one place to
   cache, retry, and normalize.

4. **Root-cause fixes over patches.** When something breaks, find and fix the
   underlying cause. Do not paper over symptoms with local workarounds.

5. **Secrets live in `.env` only.** All API keys/provider keys go in a `.env`
   file that is **gitignored and never committed**. Do not depend on OpenBB Hub
   (it is being retired). Keep the repo private regardless.

## Project layout

```
app/        FastAPI app, routers, schemas
services/   thin domain logic per view
obb_layer/  the ONLY place that imports openbb
cache/      response cache (per-data-type TTLs)
web/        frontend (later phase)
config.py   loads keys/settings from .env
```

## Working conventions

- Pin `openbb` and provider extensions; OpenBB's surface moves fast.
- Treat every number as research context, not a trade trigger. Label data
  freshness explicitly.
- Keep symbol mapping (CME ↔ yfinance continuation ↔ spot proxy) in one explicit
  config map, not scattered string literals.
- Ship each view backend-complete and cached before starting the next.
