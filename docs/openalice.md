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

## How OpenAlice consumes MCP servers

OpenAlice is built on the Claude Agent SDK and wires MCP servers into each agent
**workspace** through a **`.mcp.json`** file (workspaces live under
`~/.openalice/workspaces/<wsId>/`). Its own servers are registered by URL
(e.g. `http://localhost:47332/mcp`), so the terminal slots in as one more entry
in the standard Agent-SDK `mcpServers` schema.

> ⚠️ OpenAlice **generates** the per-workspace `.mcp.json`, so a hand-edit there
> can be overwritten. The durable place to add an external server is OpenAlice's
> own config (whatever it uses to seed `.mcp.json` for new workspaces). The entry
> below is the standard Agent-SDK format — verify the exact field names against a
> real `.mcp.json` in your install (`~/.openalice/workspaces/<wsId>/.mcp.json`).

## Option A — HTTP (recommended; matches how OpenAlice wires its own servers)

Run the terminal's MCP server over HTTP:

```powershell
python mcp_server.py --http        # serves at http://127.0.0.1:8001/mcp
```

Add it to OpenAlice's `.mcp.json`:

```json
{
  "mcpServers": {
    "market-terminal": {
      "type": "http",
      "url": "http://127.0.0.1:8001/mcp"
    }
  }
}
```

(If OpenAlice runs in Docker and can't reach `127.0.0.1`, set `MCP_HOST=0.0.0.0`
in `.env` and use the host's LAN address instead — only on a trusted network.)

## Option B — stdio (OpenAlice spawns it as a subprocess, same machine)

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

## Tools OpenAlice will see

`macro_dashboard`, `watchlist_summary`, `cot_positioning`, `cot_search`,
`term_structure`, `sector_rotation`, `market_news` — all returning research
context (EOD / delayed / weekly), **never** trade signals. The agent interprets
them; the terminal only reports.
