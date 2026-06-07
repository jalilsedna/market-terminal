# Deploying market-terminal to Railway (A8)

This puts the **research terminal** online: one service serving the web UI, the
REST API, and the MCP feed (mounted at `/mcp`) under a single domain and a
single auth gate. **Only this research service goes public** — OpenAlice and any
broker keys stay on your machine (see `docs/openalice.md`). Research flows out;
orders never flow back in.

## What's in the repo for this

| File | Purpose |
|---|---|
| `Dockerfile` | Container build (Python 3.12 + OpenBB, pinned). |
| `railway.json` | Railway build/deploy config — healthcheck `/health`. |
| `.dockerignore` | Keeps `.env`, `.git`, caches out of the image. |
| `app/auth.py` | Login (session cookie) + Bearer-token gate; no-op when unset. |
| `web/login.html` | The browser sign-in page. |

## The one hard rule: auth before public

The deploy is gated by `app/auth.py`, but **only when credentials are set**.
With `AUTH_TOKEN` and `ADMIN_PASSWORD` both empty the terminal is **open** —
fine on localhost, a data/key-leak on the internet. So on Railway these env
vars are **mandatory**, not optional. `/health` reports `auth_enabled` so you
can verify in one request.

## Step 1 — generate secrets

```bash
openssl rand -hex 32   # AUTH_TOKEN
openssl rand -hex 32   # SESSION_SECRET
# pick a strong ADMIN_PASSWORD
```

## Step 2 — create the Railway service

1. Railway → **New Project → Deploy from GitHub repo** → `jalilsedna/market-terminal`.
2. Railway detects `railway.json` / `Dockerfile` and builds the container.
   (First build is slow — OpenBB is large.)

## Step 3 — set environment variables (Railway → Variables)

**Required:**
```
AUTH_TOKEN=<the first openssl value>
ADMIN_USERNAME=<you>
ADMIN_PASSWORD=<a strong password>
SESSION_SECRET=<the second openssl value>
```
**Recommended / optional:**
```
PUBLIC_BASE_URL=https://<your-app>.up.railway.app
PRECACHE_INTERVAL_MIN=30
# Provider keys, same as local .env (read-only data keys ONLY — never broker keys):
FRED_API_KEY=...
FMP_API_KEY=...
```
Do **not** set `HOST`/`PORT` — Railway injects `$PORT` and the Dockerfile binds
`0.0.0.0:$PORT`. Never put broker / trade / withdrawal keys here; this service
is research-only.

## Step 4 — expose a domain

Railway → service → **Settings → Networking → Generate Domain**. You'll get
`https://<app>.up.railway.app`. Put that in `PUBLIC_BASE_URL`.

## Step 5 — smoke-test the public deploy

```bash
APP=https://<app>.up.railway.app
TOKEN=<AUTH_TOKEN>

# 1. health is open and confirms auth is ON
curl -s $APP/health | grep -q '"auth_enabled":true' && echo "auth ON"

# 2. the API rejects anonymous calls
curl -s -o /dev/null -w '%{http_code}\n' $APP/macro/dashboard      # -> 401

# 3. Bearer token works
curl -s -H "Authorization: Bearer $TOKEN" $APP/macro/dashboard | head -c 120

# 4. the MCP feed handshakes with the token (expects 200 + event-stream)
curl -s -o /dev/null -w '%{http_code}\n' -X POST $APP/mcp/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}}'
```

In a browser, open `$APP` → you're redirected to **`/login`** → sign in with
`ADMIN_USERNAME` / `ADMIN_PASSWORD` → the terminal loads.

## Step 6 — point Alice at the public feed

In OpenAlice's workspace `.mcp.json` (see `docs/openalice.md`), swap the local
entry for the Railway URL **with the Bearer header**:

```json
{
  "mcpServers": {
    "market-terminal": {
      "type": "streamable-http",
      "url": "https://<app>.up.railway.app/mcp",
      "headers": { "Authorization": "Bearer <AUTH_TOKEN>" }
    }
  }
}
```

Now Alice reaches the research feed from anywhere — no WSL mirrored-networking
needed. The `AUTH_TOKEN` lives only in OpenAlice's config (execution side) and
Railway's env, never in this repo.

## Notes & gotchas

- **First boot is slow:** OpenBB rebuilds its static package once on startup
  (in the lifespan, on the main thread). `healthcheckTimeout` is 300s for this.
- **Single worker:** required — the in-memory cache and the main-thread OpenBB
  warm assume one process. Scale with more *instances* behind Railway, not
  `--workers N`, only once cache is externalized (ROADMAP C2).
- **Cookies are Secure:** set behind Railway's HTTPS proxy (uvicorn runs with
  `--proxy-headers`). Logging in over plain `http://` won't persist a session —
  that only matters if you force auth on a local http run.
- **Provider reachability:** if a provider blocks Railway's egress IPs, that
  panel degrades exactly as it does locally — the circuit breaker trips and the
  view shows "unavailable" rather than hanging.
- **Rotating the token:** change `AUTH_TOKEN` in Railway, then update Alice's
  `.mcp.json`. Changing `SESSION_SECRET` logs out all browser sessions.
