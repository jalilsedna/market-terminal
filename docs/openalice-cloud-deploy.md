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

## When implementing A9

Expand this doc with provider-specific steps (Caddyfile, volume paths, migration
commands). Mark **A9** done in `ROADMAP.md` when all acceptance items pass.
