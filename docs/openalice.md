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

> ⚠️ OpenAlice **regenerates** the per-workspace `.mcp.json` on workspace
> create/regen, so a hand-edit at `~/.openalice/workspaces/workspaces/<wsId>/.mcp.json`
> survives only until the next regen. For a one-off test that's fine; to make the
> feed **durable** across every workspace, see "Making the feed durable" below.

## Making the feed durable (so every workspace gets it)

A hand-edit to one workspace's `.mcp.json` is wiped when OpenAlice regenerates
it (new workspace, or regen of the current one). To make the `market-terminal`
entry survive, add it where OpenAlice **seeds** the per-workspace `.mcp.json`
rather than to the generated file itself. In an OpenAlice checkout, find the
seed/template:

```bash
# from the OpenAlice repo root — find where the workspace .mcp.json is written
grep -rn "mcpServers" --include="*.ts" src/ scripts/
grep -rn "\.mcp\.json"  --include="*.ts" src/ scripts/
```

That points at the function that builds the workspace MCP config (it already
injects OpenAlice's own `openalice` / `openalice-workspace` servers). Add a
third static entry there:

```ts
"market-terminal": {
  type: "streamable-http",
  url: "http://127.0.0.1:8001/mcp",
},
```

Now every freshly generated workspace carries the research feed. (This edit
lives **only in the OpenAlice clone**, never in this repo — it's the execution
side. Keep it in OpenAlice's own version control / a patch note.)

**Verify after a regen:** create a new workspace, then
`cat ~/.openalice/workspaces/workspaces/<newWsId>/.mcp.json` and confirm the
`market-terminal` entry is present without any manual step.

## Option A — HTTP (recommended; matches how OpenAlice wires its own servers)

Run the terminal's MCP server over streamable-HTTP:

```powershell
python mcp_server.py --http        # serves at http://127.0.0.1:8001/mcp
```

Add it to OpenAlice's `.mcp.json` alongside its own servers. The **verified
working** entry (confirmed live — Alice's agent listed all 11 tools and called
them) uses `streamable-http`:

```json
{
  "mcpServers": {
    "market-terminal": {
      "type": "streamable-http",
      "url": "http://127.0.0.1:8001/mcp"
    }
  }
}
```

A real workspace file ends up with three entries — OpenAlice's own two
(`openalice` and `openalice-workspace`, registered by URL) plus ours:

```json
{
  "mcpServers": {
    "openalice":           { "type": "streamable-http", "url": "http://127.0.0.1:47332/mcp" },
    "openalice-workspace": { "type": "streamable-http", "url": "http://127.0.0.1:47332/mcp/<wsId>" },
    "market-terminal":     { "type": "streamable-http", "url": "http://127.0.0.1:8001/mcp" }
  }
}
```

(If OpenAlice runs in Docker and can't reach `127.0.0.1`, set `MCP_HOST=0.0.0.0`
in `.env` and use the host's LAN address instead — only on a trusted network.
On WSL2 with mirrored networking, `127.0.0.1` already bridges WSL↔Windows, so
no change is needed — see `docs/openalice-wsl-setup.md`.)

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

All 11, all returning research context (EOD / delayed / weekly), **never** trade
signals. The agent interprets them; the terminal only reports.

**Raw data (7):** `macro_dashboard`, `watchlist_summary`, `cot_positioning`,
`cot_search`, `term_structure`, `sector_rotation`, `market_news`.

**Interpreted analysis layer (4):** `analysis_cot` (crowded long/short vs
1y/3y percentile), `analysis_regime` (risk-on/off vote), `analysis_brief`
(per-instrument "what's moving this contract"), `analysis_term_structure`
(contango↔backwardation flips). Every analysis response carries the disclaimer:
*"Research context only — interpreted positioning/regime signals, not investment
advice or a trade trigger."*

## The execution side (paper trading) — for reference only

Execution lives entirely in OpenAlice and is documented here only so the
boundary is clear. OpenAlice has **no mock broker**; the safe paper path is an
**Alpaca paper** account in its UTA (paper keys are prefixed `PK…`, hit
`paper-api.alpaca.markets`, and physically cannot place a real order). The
proven end-to-end loop:

1. Alice's agent pulls interpreted research from this terminal over MCP.
2. It reasons (e.g. reads a non-crowded gold-COT base + a gold-supportive
   regime, but sizes small because commercials are heavily short).
3. It stages a small paper order; a human approves via the OpenAlice Web UI.
4. Alpaca paper fills it (market orders are **rejected** outside market hours —
   expected, not a bug; use a limit + extended-hours, or wait for the open).

**None of this touches market-terminal.** No broker keys, no order entry, no
position state ever live in this repo — only the read-only research feed flows
out. See `docs/openalice-wsl-setup.md` for the full host setup.
