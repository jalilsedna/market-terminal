# CLAUDE.md

Guidance for Claude (and any AI/automation) working in this repository.

## What this is

A **private, single-user Python research terminal** for multi-asset market
research and analytics. It is built **on top of OpenBB**, which we consume as a
**library** (`pip install openbb`) — never as a fork.

- **Stack:** Python 3.12 · FastAPI · OpenBB Platform
- **Scope:** multi-asset *research* (macro, market data, positioning,
  fundamentals of futures underlyings/sectors, news).
- **Execution is delegated, not duplicated.** This terminal is the *research
  brain*: it does **not** place/route/manage orders or hold broker connectivity,
  and **no trade/transfer/withdrawal-capable keys ever live here** (only
  read-only data keys). Execution is a separate system — OpenAlice (which pulls
  this terminal's research over MCP — see `docs/openalice.md`), NinjaTrader, or
  MetaTrader. The split is deliberate: research and execution have different
  risk profiles, so orders flow there, never from here. Changing this is a
  conscious, documented decision — not an incidental feature add.

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
app/        FastAPI app, routers, schemas, auth, pre-cache scheduler
services/   thin domain logic per view (incl. analysis, alerts, movers, doctor)
obb_layer/  provider-integration layer: the ONLY place that imports openbb, plus
            direct provider clients where OpenBB falls short (e.g. grouped.py —
            Polygon Grouped Daily REST) and the symbol maps
vol/        volatility/regime models (pure numpy — realized vol, HAR/EWMA, regime)
cache/      in-process response cache (per-data-type TTLs)
web/        single-page dashboard (vanilla JS) + login/register pages
tests/      pytest suite (lightweight, no-OpenBB) — CI-gated
docs/       deploy, data-provider, OpenAlice, and operator guides
scripts/    eval + ops tools (probe_providers, eval_vol, …)
mcp_server.py  exposes the views as MCP tools (stdio or HTTP)
config.py   loads keys/settings from .env
```

## Working conventions

- Pin `openbb` and provider extensions; OpenBB's surface moves fast.
- Treat every number as research context, not a trade trigger. Label data
  freshness explicitly.
- Keep symbol mapping in explicit config maps, never scattered literals: the
  futures map (`obb_layer/symbols.py` — CME ↔ yfinance ↔ spot proxy ↔ TradingView)
  and the per-provider crypto/FX formats (`obb_layer/symbol_map.py`).
- Provider reliability is a chain: equity/ETF and crypto/FX fetchers fall back
  across `EOD_PROVIDERS` (`obb_layer/providers.py`); add new providers there.
- Ship each view backend-complete and cached before starting the next.

## Keeping this in sync (ROADMAP D1)

This file is the **canonical** guidance. Mirror it into the claude.ai **Project
instructions** (and any other agent config) so web, IDE, and CLI sessions all
follow the same rules — when you change CLAUDE.md, update the Project
instructions to match. `SPEC.md` (product spec) and `ROADMAP.md` (backlog +
done-ledger) are the other living docs; keep all three honest as the product
moves.
