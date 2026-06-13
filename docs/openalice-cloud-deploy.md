# OpenAlice — cloud deploy (24/7 execution, browser from anywhere)

**ROADMAP A9.** Research stays on **market-terminal (Railway, A8)**; execution,
monitoring, inbox, and paper approval move to an **always-on OpenAlice host** so
the loop works when your laptop is off.

See also: [`openalice.md`](openalice.md), [`openalice-multi-broker.md`](openalice-multi-broker.md),
[`deploy-railway.md`](deploy-railway.md), [`openalice-wsl-setup.md`](openalice-wsl-setup.md),
OpenAlice upstream `README` → "Run on a server (Docker)".

---

## Target topology

```
Browser (any device)
  → https://alice.<your-domain>     OpenAlice (Docker on VPS)
       ├─ UTA(s) — Alpaca paper; IBKR if forex/metals (Gateway on same host)
       ├─ Workspaces + cron (scheduled monitoring)
       └─ MCP → https://<railway-app>.up.railway.app/mcp/  (Bearer AUTH_TOKEN)

market-terminal (Railway) — research only, no broker keys
```

---

## Host options (pick one)

The CPU is the only hard gate: the `claude` agent runtime needs **AVX2**, or it
crashes `illegal instruction`. Two budget VPS attempts failed because the provider
**masked the CPU** (`lscpu` → "Common KVM processor", no AVX flags) — a config the
guest can't override. Verify AVX2 *before* committing to any host:
`grep -o avx2 /proc/cpuinfo | head -1` (Linux) — must print `avx2`.

| Option | AVX2 | Effort | Notes |
|--------|------|--------|-------|
| **Railway (managed)** | ✅ guaranteed (GCP hosts; verified via `/health` `cpu_avx2:true`) | medium | No CPU lottery; multi-service mapping is the work. **See below.** |
| **Linux VPS + Docker** | ⚠️ verify first | low | Cheapest/cleanest *if* the provider exposes AVX2 (Hetzner/DO/Vultr). Official OpenAlice path. |
| **Windows Server + WSL2** | ⚠️ verify first | high | See "Windows Server + WSL2" section; needs nested virt **and** AVX2. |

---

## Railway deploy (managed host — AVX2 guaranteed)

Chosen path after budget VPS providers masked the CPU. Railway runs on GCP, which
exposes AVX2 (confirmed: market-terminal `/health` reports `"cpu_avx2": true`), so
the agent runtime runs. OpenAlice's `docker-compose.yml` is actually a **single
container** (the app), so it's **one Railway service** — plus a second service for
the headless IB Gateway. The recipe below is the **validated, confirmed-working**
sequence (June 2026), including the non-obvious gotchas.

### Boundary (non-negotiable)

Deploy OpenAlice as a **separate Railway project** from market-terminal. Broker
(paper) keys live **only** in the OpenAlice project's variables — **never** in
market-terminal (CLAUDE.md hard rule: no trade-capable keys in the research app).
Research ↔ execution stay separate apps even on the same platform.

### Services (map from OpenAlice's `docker-compose.yml`)

1. **`openalice` (app)** — build from the OpenAlice repo (Dockerfile). Attach a
   **Railway Volume** at OpenAlice's `data/` path so `accounts.json`, `persona.md`,
   workspaces, and the inbox survive redeploys. Public domain for the Web UI
   (admin-token login).
2. **`ib-gateway`** — the headless **[`ib-gateway-docker`](https://github.com/gnzsnz/ib-gateway-docker)**
   image (IBC auto-login + Xvfb, no GUI). `TRADING_MODE=paper`, IBKR paper creds via
   env. **Private network only** (the IB API socket has no auth). Because Railway's
   private network is IPv6 and the image's socat is IPv4-only, you add an IPv6
   listener (see recipe step 11) and the `openalice` service reaches it at
   `ib-gateway.railway.internal:4006`. The paper account re-connects here and gets a
   **new UTA id** (update prompts/persona).
3. *(optional)* a reverse-proxy service if you want a custom domain; Railway's
   per-service HTTPS domain is usually enough.

### Agent auth (no per-token bill)

The `claude` CLI authenticates with your **Claude subscription**, not a paid API
key. On a headless container: run `claude setup-token` once locally, then set the
resulting token as an env var on the `openalice` service (per Claude Code's
headless auth) so the agent runs without a browser. The pay-per-token
`ANTHROPIC_API_KEY` is **only** for market-terminal's optional News Pulse analyst —
not required for the agent.

### Variables (on the `openalice` project, not market-terminal)

| Var | Purpose |
|-----|---------|
| `CLAUDE_CODE_OAUTH_TOKEN` (or equivalent) | headless `claude` auth via your subscription |
| Alpaca **paper** key + secret | `alpaca` UTA |
| IBKR paper user/pass, `TRADING_MODE=paper` | `ib-gateway` (IBC) |
| market-terminal MCP URL + `AUTH_TOKEN` | workspace `.mcp.json` → research |
| OpenAlice admin token / session secret | Web UI login |

Workspace `.mcp.json` entry (points at the research terminal):

```json
{
  "market-terminal": {
    "type": "streamable-http",
    "url": "https://<railway-app>.up.railway.app/mcp/",
    "headers": { "Authorization": "Bearer <AUTH_TOKEN>" }
  }
}
```

### Smoke tests (Railway)

- [ ] OpenAlice Web UI loads over its Railway HTTPS domain; admin-token login works
- [ ] `openalice` logs show `connected` for both Alpaca and `IbkrBroker[ibkr-…]`
- [ ] Workspace MCP: `analysis_regime`, `decision_brief("forex:EURUSD")`
- [ ] `getPortfolio source: ibkr-…` (private-network reach to `ib-gateway`) + `source: alpaca-…`
- [ ] A cron job fires with your laptop off → inbox entry
- [ ] Redeploy the `openalice` service → `data/` (accounts/workspaces) survives (Volume)

### Validated build recipe + gotchas (confirmed working, June 2026)

The exact sequence that worked, with the traps that cost time:

1. **AVX2 first.** Verify any host before building (`grep -o avx2 /proc/cpuinfo`).
   Railway/GCP passes; two budget VPS ("Common KVM processor") masked it and were
   dead ends. market-terminal `/health` now reports `cpu_avx2`.

2. **Fork the repo** to your GitHub (Railway builds from a repo you own).

3. **Drop the Dockerfile `VOLUME` instruction.** Railway rejects builds with
   `VOLUME` (`dockerfile invalid: docker VOLUME ... is not supported, use Railway
   Volumes`). Comment out the `VOLUME /data` line in your fork's Dockerfile, commit.
   Persistence comes from a Railway Volume instead.

4. **One service, root Dockerfile.** If Railway auto-splits the monorepo into
   multiple services (`desktop`/`ui`/`uta-service`), delete them and create **one**
   service with **Root Directory `/`** + **Builder = Dockerfile**.

5. **Volume + `OPENALICE_HOME`.** Attach a Railway Volume at **`/data`** and set
   `OPENALICE_HOME=/data`. Note OpenAlice then stores state under **`/data/data/`**
   (config, `workspaces/`, `home/.claude*`) — double `data` is expected.

6. **Variables** on the app service: `OPENALICE_BIND_HOST=0.0.0.0`,
   `OPENALICE_HOME=/data`, `CLAUDE_CODE_OAUTH_TOKEN=<claude setup-token>`, and after
   you generate the domain: `OPENALICE_CSRF_TRUSTED_ORIGINS=https://<domain>`,
   `WEB_TERMINAL_ALLOWED_ORIGINS=https://<domain>`, `OPENALICE_TRUSTED_PROXIES=0.0.0.0/0`.

7. **Expose the Web UI on port `47331`** (Settings → Networking → Generate Domain →
   target port 47331). MCP `47332` stays private.

8. **Admin token** prints once on first boot to the deploy logs. If missed, the
   hash lives at `/data/data/config/auth.json` (not the plaintext) — regenerate by
   `rm /data/data/config/auth.json` + restart, then grab the new token from logs.
   Auth gate is real (verify in an incognito window — it should demand the token).

9. **MCP wiring + durability.** Add market-terminal to the agent. Per-workspace
   `.mcp.json` lives at `/data/workspaces/workspaces/<uuid>/.mcp.json`, but the
   template is **baked into the image** (new chats regenerate without it). The
   durable fix: add market-terminal to the **user-scoped** `/data/home/.claude.json`
   `mcpServers` (read by every session, survives redeploys), **and** set
   `enableAllProjectMcpServers: true` in `/data/home/.claude/settings.json` (else
   Claude Code silently skips unapproved project `.mcp.json` servers).

10. **IB Gateway service** (`ghcr.io/gnzsnz/ib-gateway:stable`): env `TWS_USERID`,
    `TWS_PASSWORD`, `TRADING_MODE=paper`, `READ_ONLY_API=no`. **Do not** expose it
    publicly (the IB API socket has no auth).

11. **IPv6 gotcha (the big one).** Railway's private network is **IPv6**, but the
    image's socat binds IPv4 (`0.0.0.0:4004`) → OpenAlice can't reach it. Fix with a
    Railway **Custom Start Command** that adds an IPv6 listener, then connect
    OpenAlice's IBKR UTA to that port:
    ```
    sh -c "socat TCP6-LISTEN:4006,fork,reuseaddr TCP4:127.0.0.1:4004 & exec /home/ibgateway/scripts/run.sh"
    ```
    IBKR host = `ib-gateway.railway.internal`, **port `4006`**, Client ID `1`.

12. **One IBKR session per login.** If your **local** Gateway/TWS is still logged in
    with the same credentials, the cloud Gateway connect/disconnect-flaps as they
    fight for the single allowed session. Keep the local Gateway **off**; cloud is
    the live one. Enable IBC auto-restart so it re-auths through IBKR's daily reset.

### Cost note

Two always-on services (app + gateway) plus the agent's work is real usage — budget
for Railway's metered/Pro tier, not hobby. Still typically cheaper than a Windows
VPS with licensing, and with **zero** CPU-masking risk.

---

## Prerequisites

- VPS or always-on Linux host (US region fine for Alpaca paper)
- Domain + DNS (for HTTPS)
- Railway market-terminal already live (A8)
- Alpaca **paper** keys (`PK…`) — OpenAlice side only

---

## Checklist (A9 acceptance)

### 1. Deploy OpenAlice (Docker)

```bash
git clone https://github.com/TraderAlice/OpenAlice.git
cd OpenAlice
docker compose up -d --build
docker logs openalice 2>&1 | grep -A1 'admin token'   # first boot only
```

- Persistent volume for `data/` (config, workspaces, UTA, inbox)
- Apply local patches on the server if needed (e.g. `dataUTAs: []` in
  `services/uta/src/main.ts` to skip geo-blocked CCXT readonly feeds)

### 2. HTTPS (public browser access)

- Reverse proxy (Caddy or nginx) → OpenAlice web port (`47331`)
- TLS (Let's Encrypt)
- **Do not** expose MCP `47332` publicly (localhost / container only)
- Log in with admin token; session cookie ~7 days

### 3. Migrate from local WSL

Copy to server `data/` volume:

| Item | Source (typical) |
|------|------------------|
| Alpaca account | `data/config/accounts.json` |
| Persona | `data/brain/persona.md` |
| Workspaces | `~/.openalice/workspaces/` |
| Railway MCP | workspace `.mcp.json` or OpenAlice seed template |

Workspace MCP entry:

```json
{
  "market-terminal": {
    "type": "streamable-http",
    "url": "https://<railway-app>.up.railway.app/mcp/",
    "headers": { "Authorization": "Bearer <AUTH_TOKEN>" }
  }
}
```

Portfolio tools: always pass `source: <uta-id>` per broker (Alpaca equities,
IBKR forex/metals — see `docs/openalice-workflow.md`, `docs/openalice-multi-broker.md`).

### 4. Smoke tests (server)

- [ ] Web UI login from a phone/laptop (not the VPS)
- [ ] Workspace MCP: `analysis_regime`, `decision_brief`
- [ ] `getPortfolio` / `getAccount` with Alpaca `source`
- [ ] One cron job runs with dev PC off → inbox entry

### 5. Security

- HTTPS only; strong admin token
- Paper keys only until deliberate go-live
- Rotate keys after any copy over network or chat leak
- Never put broker keys in market-terminal / Railway

---

## Out of scope (A9)

- OpenAlice on Railway (possible later; official path is VPS + Docker)
- Live (non-paper) brokers
- Inbox prompt-vs-proposal display fix (parked)

---

## Windows Server + WSL2 (full always-on agent) — chosen host

The Docker/Linux path above is the lightest. This section is the **Windows Server**
variant for a **full always-on agent** (OpenAlice + the `claude` CLI + IB Gateway
all running 24/7, so Alice can scan *and* enter around the clock). Chosen for RDP
comfort + native IB Gateway GUI. It's heavier and has two Windows-specific traps
(headless WSL keep-alive, WSLg on Server SKUs) — both solved below.

> **⚠️ CPU requirement is unchanged: the host MUST have AVX2.** Our earlier VPS
> failed because its CPU lacked AVX — the `claude` CLI runtime (Node/Bun + native
> binaries) crashes with `illegal instruction` without it. **Windows does not fix
> this** — AVX2 is a processor feature, not an OS feature. A Windows VM on a
> non-AVX2 host fails identically. **Verify before paying for a year.**

### 0. Pick + verify the VM

- 4 vCPU / 16 GB RAM minimum (Windows + WSL2 + Gateway + OpenAlice + `claude` is
  hungry); 50 GB+ disk. US region is fine for Alpaca/IBKR paper.
- **Windows Server 2022 or 2025** with the **Desktop Experience** (you need a
  desktop session for RDP + WSLg). Server 2025 has the smoothest WSLg.
- Providers with modern (AVX2) CPUs + Windows images: **Azure** (often cheapest
  Windows licensing), **AWS EC2 Windows**, **GCP**, **Vultr**. Avoid bargain
  "legacy"/OpenVZ tiers — that's where non-AVX2 CPUs hide.
- **Verify AVX2 the moment you can RDP in**, before configuring anything:
  - PowerShell (Sysinternals): `coreinfo64.exe -f | findstr AVX2` → want a `*`.
  - or after WSL is installed: `grep -o avx2 /proc/cpuinfo | head -1` → `avx2`.
  - No AVX2 → **stop, rebuild on a different instance type.** Do not proceed.

### 1. Enable WSL2 + Ubuntu (PowerShell as admin)

```powershell
wsl --install -d Ubuntu        # installs WSL2 + Ubuntu; reboot if prompted
wsl --update                    # ensures the latest WSL (WSLg / systemd support)
wsl --set-default-version 2
```

Create the Ubuntu user when it launches. Cap WSL memory in `C:\Users\<you>\.wslconfig`:

```ini
[wsl2]
memory=12GB
processors=4
# Leave networking default (NAT). Do NOT use networkingMode=mirrored — it breaks
# the browser→UI localhost forwarding (see openalice-multi-broker.md).
```

### 2. Build OpenAlice + the agent inside WSL

Follow [`openalice-wsl-setup.md`](openalice-wsl-setup.md) verbatim — it's the same
Ubuntu inside WSL, just on a server. In short:

```bash
sudo apt update && sudo apt install -y build-essential make gcc git curl  # node-pty needs a compiler
# Node 20 + pnpm (per wsl-setup doc), then:
git clone https://github.com/TraderAlice/OpenAlice.git ~/OpenAlice
cd ~/OpenAlice && pnpm install
claude            # log the agent runtime in ONCE (interactive, over RDP) — verifies AVX2 works
```

If `claude` throws `Illegal instruction (core dumped)` → the CPU lacks AVX2 (step 0). Rebuild the VM.

### 3. Make WSL services survive reboots — **enable systemd**

`/etc/wsl.conf` inside Ubuntu:

```ini
[boot]
systemd=true
```

Then `wsl --shutdown` (PowerShell) and relaunch Ubuntu. Run OpenAlice as a service
(pm2 or a systemd unit) so it starts with the distro:

```bash
# simplest: pm2 keeps OpenAlice + restarts on crash
sudo npm i -g pm2
cd ~/OpenAlice && pm2 start "pnpm dev" --name openalice && pm2 save
pm2 startup systemd   # follow the printed command so pm2 resurrects on boot
```

### 4. The Windows trap — keep WSL running with **no user logged in**

A WSL2 distro shuts down when its last process exits / no console holds it open,
so after an RDP logoff your "always-on" agent dies. Fix: a **Task Scheduler** task
that boots the distro headlessly at machine start.

- Task Scheduler → Create Task → **Run whether user is logged on or not**,
  **Run with highest privileges**, Trigger: **At startup**.
- Action: `Program: wsl.exe`  ·  `Arguments: -d Ubuntu -u root -e sh -c "tail -f /dev/null"`
  (a tiny keep-alive that holds the distro up; systemd + pm2 then run OpenAlice).

Now OpenAlice + Gateway run after a reboot even before anyone RDPs in.

### 5. IB Gateway 24/7 (forex/metals)

Two options — pick one:

- **GUI in WSLg (familiar):** run the Linux Gateway inside WSL exactly as in
  [`openalice-multi-broker.md`](openalice-multi-broker.md) (`~/Jts/ibgateway/*/ibgateway &`,
  port 4002 paper, localhost). Needs an active desktop session (RDP) for WSLg to
  render — fine if you RDP daily, fragile for true headless.
- **Headless auto-login (recommended for a server):** drive Gateway with **IBC
  (IBController)** so it logs in and auto-restarts without GUI clicks, as a systemd
  service in WSL. Survives reboots and IB's daily server reset. Still `127.0.0.1:4002`.

Either way: API on, Read-Only **off**, Trusted IP `127.0.0.1`. Confirm:
`timeout 2 bash -c "</dev/tcp/127.0.0.1/4002" && echo OPEN`.

### 6. HTTPS browser access from anywhere

- Run **Caddy inside WSL** (auto-TLS) reverse-proxying `https://alice.<domain>` →
  OpenAlice web port `47331`. Point DNS at the VM's public IP; open 80/443 in the
  cloud firewall + Windows Defender.
- **Do not** expose MCP `47332` — keep it localhost/container only.
- If you proxy from the Windows side instead, bridge to WSL with
  `netsh interface portproxy add v4tov4 ...` (NAT mode). Prefer Caddy-in-WSL to
  avoid the port-proxy dance.

### 7. Migrate state + smoke test

Same as the Docker checklist above (§3/§4): copy `accounts.json`, `persona.md`,
workspaces, and the workspace `.mcp.json` (Railway MCP Bearer) onto the box; then:

- [ ] RDP **logged off** → reboot → confirm OpenAlice UI answers (Task Scheduler + pm2 worked)
- [ ] Web UI login from a phone over HTTPS
- [ ] Workspace MCP: `analysis_regime`, `decision_brief("forex:EURUSD")`
- [ ] `getPortfolio source: ibkr-tws-…` and `source: alpaca-61b238e3`
- [ ] One cron job fires with your laptop off → inbox entry
- [ ] Gateway reconnects after a reboot (IBC) or after RDP login (WSLg)

### Honest tradeoff note

This works, but it's the heavier path: Windows licensing cost, ~2× the RAM
footprint, the headless-WSL keep-alive, and WSLg's desktop-session dependency for
the Gateway GUI (use IBC to dodge it). A small **Ubuntu VM + Docker Compose** (top
of this doc) avoids all of that for the same agent. Revisit if the Windows overhead
bites — the migration is just copying the `data/` volume.

---

## When implementing A9

Expand this doc with provider-specific steps (Caddyfile, volume paths, migration
commands). Mark **A9** done in `ROADMAP.md` when all acceptance items pass.
