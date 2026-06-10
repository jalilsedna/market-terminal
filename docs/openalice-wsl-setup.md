# Running OpenAlice on WSL2 (reproducible setup)

OpenAlice (the **execution** agent — see `docs/openalice.md`) needs a Linux
host: its agent bootstrap uses a POSIX shell and it spawns Claude Code through
`node-pty`, which doesn't work cleanly on native Windows. The clean answer on a
Windows machine is **WSL2 + Ubuntu**. This is the host setup that got the
research → reason → paper-execute loop working end to end.

> This document describes the **OpenAlice host** (the execution side). It lives
> in this repo only so the integration is reproducible. Nothing here installs or
> changes market-terminal, and **no broker keys ever come into this repo.**

## 1. WSL2 + Ubuntu

From an elevated PowerShell on Windows 11:

```powershell
wsl --update                 # fixes kernel error 0x800701bc on older WSL
wsl --install -d Ubuntu      # install the distro
ubuntu                       # launch it (registers the distro, sets up user)
```

## 2. Build toolchain (for node-pty)

Inside Ubuntu — `node-pty` compiles native code, so without `make`/gcc it fails
with `not found: make`:

```bash
sudo apt update
sudo apt install -y build-essential
```

## 3. Node 22 + pnpm, then OpenAlice

OpenAlice is a Node 22 / pnpm / TypeScript monorepo. Install Node 22 (nvm or
NodeSource), enable pnpm via corepack, then:

```bash
git clone https://github.com/TraderAlice/OpenAlice.git
cd OpenAlice
corepack enable
pnpm install
```

## 4. Claude Code login (the agent runtime)

OpenAlice spawns **Claude Code** as its agent. Log in once inside WSL so the
spawned agent inherits the session:

```bash
claude        # then follow the login prompt
```

## 4b. Cursor Agent CLI (fallback when Claude limits out)

When Claude Code hits its usage cap, continue in the **same workspace** with
Cursor — market-terminal MCP still works.

```bash
curl https://cursor.com/install -fsS | bash
agent login
agent status
```

Optional auto-fallback script (from this repo):

```bash
chmod +x ~/market-terminal/scripts/openalice-claude-or-cursor.sh
```

See **`docs/openalice-cursor-fallback.md`** (persona snippet for Alice, MCP
verify, Railway vs local URLs).

## 5. The 60s UTA timeout edit (OpenAlice clone only)

On first boot the guardian sometimes fails with *"UTA failed to come up within
15s"* because the cold start is slow. Bump the timeout — this edit lives **only
in the OpenAlice checkout**, not here:

```bash
# in the OpenAlice repo
sed -i 's/timeoutMs: 15_000/timeoutMs: 60_000/' scripts/guardian/dev.ts
```

## 6. Mirrored networking — the bridge to the research feed

market-terminal's MCP server runs on **Windows** at `127.0.0.1:8001`; OpenAlice's
agent runs in **WSL**. WSL2 **mirrored networking** makes WSL `localhost` ==
Windows `localhost` (Windows 11 22H2+), so the agent reaches the feed at
`http://127.0.0.1:8001/mcp` with no LAN address or port-forwarding.

Create / edit `C:\Users\<you>\.wslconfig` on the **Windows** side:

```ini
[wsl2]
networkingMode=mirrored
```

Then `wsl --shutdown` from PowerShell and relaunch Ubuntu for it to take effect.

## 7. Run it

```bash
cd OpenAlice
pnpm dev
```

The guardian spawns: **UTA** (`:47333`), **Alice** (`:47331`), **MCP**
(`:47332`), and the **Vite UI** (`:5173`). Open `http://localhost:5173` from
Windows.

## 8. Wire in the research feed

On Windows, start the terminal's MCP server:

```powershell
python mcp_server.py --http       # http://127.0.0.1:8001/mcp
```

Then add the `market-terminal` entry to OpenAlice's workspace `.mcp.json` (see
`docs/openalice.md` → "Making the feed durable" so it survives regen).

## Verify the loop

In an Alice workspace, confirm the agent sees the feed and can reason over it:

> List the market-terminal tools, then give me the gold COT read and the macro
> regime.

You should see it call `cot_positioning` / `analysis_cot` + `analysis_regime`
and return the interpreted reads with the disclaimer intact. That's the feed
live. Paper execution (Alpaca paper account in the UTA) is covered in
`docs/openalice.md`.

## Troubleshooting quick-reference

| Symptom | Cause | Fix |
|---|---|---|
| `0x800701bc` on `wsl --install` | stale WSL kernel | `wsl --update` |
| distro never registers | install didn't finish | `wsl --install -d Ubuntu`, then launch `ubuntu` |
| `node-pty` → `not found: make` | no build toolchain | `sudo apt install -y build-essential` |
| `UTA failed to come up within 15s` | slow cold start | bump timeout to `60_000` (step 5) |
| agent can't reach `127.0.0.1:8001` | no mirrored networking | `.wslconfig` `networkingMode=mirrored` + `wsl --shutdown` |
| Claude **rate limit** / 429 | Anthropic quota exhausted | run `agent` in workspace, or `scripts/openalice-claude-or-cursor.sh` — see `docs/openalice-cursor-fallback.md` |
| Alpaca paper order **rejected** | market closed (market order) | use limit + extended-hours, or wait for the open |
