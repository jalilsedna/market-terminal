# Connecting market-terminal to OpenAlice

[OpenAlice](https://github.com/TraderAlice/OpenAlice) is a separate, AGPL-3.0 **AI
trading agent** that handles research → **execution** → position management across
brokers. market-terminal is **research and analytics only** — it never places,
routes, or simulates trades (see `CLAUDE.md` and `SPEC.md`).

So the two are wired at the **boundary**, exactly like the spec's separation of
research from execution (NinjaTrader / MetaTrader). market-terminal is a **research
data source** that OpenAlice *pulls from* over MCP. Nothing flows the other way:

```
  market-terminal (this repo)                 OpenAlice (separate app)
  research only · read-only keys               execution · broker keys
  ┌──────────────────────────┐   MCP (tools)  ┌────────────────────────┐
  │ macro · watchlist · COT   │ ─────────────▶ │ agent reads research,  │
  │ term structure · sectors  │   research     │ decides, and EXECUTES  │
  │ news   (mcp_server.py)     │   flows out    │ on its own broker side │
  └──────────────────────────┘                └────────────────────────┘
        ▲ no orders, no broker creds, ever cross this line ▲
```

**Hard boundary (do not cross):** no order entry, position management, broker
connectivity, or trade/transfer/withdrawal keys ever live in market-terminal. If
you want execution, it belongs in OpenAlice, on its side.

## Option A — HTTP (recommended; OpenAlice as a separate service / container)

Run the terminal's MCP server over HTTP:

```powershell
python mcp_server.py --http        # serves at http://127.0.0.1:8001/mcp
```

Point OpenAlice at that URL as a **streamable-HTTP MCP server** named
`market-terminal`. (If OpenAlice runs in Docker and can't reach `127.0.0.1`, set
`MCP_HOST=0.0.0.0` in `.env` and use the host's LAN address — only on a trusted
network.)

## Option B — stdio (OpenAlice spawns it as a subprocess, same machine)

Register a stdio MCP server in OpenAlice that runs:

```
command: <abs path>\.venv\Scripts\python.exe
args:    [ <abs path>\mcp_server.py ]
```

## Tools OpenAlice will see

`macro_dashboard`, `watchlist_summary`, `cot_positioning`, `cot_search`,
`term_structure`, `sector_rotation`, `market_news` — all returning research
context (EOD / delayed / weekly), **never** trade signals. The agent interprets
them; the terminal only reports.
