# OpenAlice → Cursor when Claude Code limits out

OpenAlice workspaces run a **native agent CLI** (default: **Claude Code** /
`claude`). Anthropic Pro/Max caps show up as HTTP 429, *"rate limit"*, or
*"usage limit reached"* mid-session. **OpenAlice does not auto-switch providers**
today — you wire the fallback once on the execution side (OpenAlice host), not in
market-terminal.

market-terminal is unchanged: the same `market-terminal` MCP feed works from
**both** Claude Code and **Cursor Agent** (`agent` CLI) as long as
`.mcp.json` is present in the workspace.

---

## Quick fix (when you are already rate-limited)

In the **same OpenAlice workspace** terminal:

```bash
agent
```

If `agent` is not installed:

```bash
curl https://cursor.com/install -fsS | bash
agent login    # once per machine
agent
```

Then re-ask the same research question. Cursor reads the workspace
`.mcp.json`, so `market-terminal` tools (`cot_positioning`, `brain_verdict`,
`term_structure`, …) still work.

---

## One-time setup (WSL / Linux host)

### 1. Install Cursor Agent CLI

```bash
curl https://cursor.com/install -fsS | bash
agent login
agent status    # should show you are authenticated
```

### 2. Keep Claude Code as primary

You already did this for OpenAlice (`claude` login) — see
`docs/openalice-wsl-setup.md`.

### 3. Optional — automatic fallback script

From your market-terminal clone:

```bash
chmod +x scripts/openalice-claude-or-cursor.sh
```

**Manual use** when Claude dies on a limit:

```bash
bash ~/market-terminal/scripts/openalice-claude-or-cursor.sh
```

**Shell workspace pattern:** create an OpenAlice workspace with agent CLI =
`shell`, then start with:

```bash
bash ~/market-terminal/scripts/openalice-claude-or-cursor.sh
```

The script tries `claude` first; on limit errors it restarts the session with
`agent` (Cursor).

---

## Tell Alice in persona (recommended)

OpenAlice reads `data/brain/persona.md` (user override). Add this block in your
**OpenAlice clone** (not this repo):

```markdown
## Claude Code rate limits → Cursor

When Anthropic usage is exhausted (429, "rate limit", "usage cap", or Claude Code
refuses to run):

1. Tell the operator clearly that **Claude Code quota is hit**.
2. Instruct them to continue in **Cursor Agent** in this workspace:
   run `agent` in the workspace terminal (or use `scripts/openalice-claude-or-cursor.sh`
   from market-terminal).
3. **Do not stop research** — re-call the same `market-terminal` MCP tools from
   Cursor; the feed is the same `.mcp.json` entry.
4. Execution (orders) still flows through OpenAlice UTA approval — unchanged.
```

Path on the OpenAlice host: `OpenAlice/data/brain/persona.md` (gitignored
override; copy from `default/persona.default.md` on first boot if missing).

---

## MCP in Cursor

Cursor Agent shares MCP config with the workspace. After `agent login`:

```bash
# inside the workspace directory
agent mcp list
```

You should see OpenAlice's servers plus `market-terminal` (if seeded per
`docs/openalice.md`). If `market-terminal` is missing after a workspace regen,
re-add it to OpenAlice's workspace seed or hand-fix `.mcp.json` once, then
`agent mcp enable market-terminal` if needed.

Railway-hosted feed (production):

```json
"market-terminal": {
  "type": "streamable-http",
  "url": "https://YOUR-RAILWAY-APP.up.railway.app/mcp",
  "headers": { "Authorization": "Bearer YOUR_AUTH_TOKEN" }
}
```

Local dev feed:

```json
"market-terminal": {
  "type": "streamable-http",
  "url": "http://127.0.0.1:8001/mcp"
}
```

---

## What does *not* switch automatically

| Layer | On limit |
|-------|----------|
| **market-terminal** | Keeps serving MCP — no change |
| **OpenAlice UTA / paper** | Keeps running — no change |
| **Claude Code CLI** | Stops until quota resets or you use Cursor |
| **Cursor `agent`** | Separate subscription quota — use when Claude is capped |

There is no setting in market-terminal to "point Alice to Cursor"; the switch
happens on the **OpenAlice workspace CLI** (manual `agent` or the fallback
script above).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `agent: command not found` | Run Cursor install + reopen shell (`curl … \| bash`) |
| Cursor can't see MCP tools | `agent mcp list`; enable servers; check `.mcp.json` |
| `market-terminal` 401 on Railway | Set `Authorization: Bearer` + `AUTH_TOKEN` in `.mcp.json` |
| Claude works but Cursor doesn't login | `agent login` in the same WSL session as OpenAlice |
| Want Codex instead of Cursor | OpenAlice also supports `codex` workspace CLI — `codex login` |

See also: `docs/openalice.md`, `docs/openalice-wsl-setup.md`,
`docs/deploy-railway.md` (public MCP URL).
