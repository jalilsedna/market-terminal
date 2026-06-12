# OpenAlice — multi-broker execution (forex, metals, equities)

**ROADMAP A10.** market-terminal is **research-only** (Railway, MCP). **Execution**
lives in OpenAlice on your machine (or A9 VPS). Alpaca paper covers **US stocks +
limited crypto** — not spot forex or COMEX metals. This doc maps **which brokers
OpenAlice supports**, how to run **multiple UTAs** side by side, and how to wire
the research → execution loop for a **forex + metals** book.

See also: [`openalice.md`](openalice.md), [`openalice-workflow.md`](openalice-workflow.md),
[`openalice-cloud-deploy.md`](openalice-cloud-deploy.md), [`openalice-wsl-setup.md`](openalice-wsl-setup.md).

---

## The problem

| Your focus | Alpaca paper | market-terminal research |
|------------|--------------|--------------------------|
| US equities / ETFs | ✅ execute | ✅ `trade_setup`, `brain_*`, `decision_brief` |
| Crypto (BTC, ETH, …) | ⚠️ limited pair set | ✅ `market_setup`, `crypto_brain_*` |
| **Spot forex** (EURUSD, USDJPY, …) | ❌ not supported | ✅ `market_setup`, `forex_brain_*`, `decision_brief` |
| **Metals** (gold, silver) | ❌ not supported | ✅ GC COT, macro; execute via broker |

Research and execution must use **different UTAs** when asset classes differ.
One `getPortfolio` call without `source` often fails or returns the wrong account
when several brokers are configured.

---

## Architecture

```mermaid
flowchart TB
  MT["market-terminal (Railway)\n35 MCP tools · research only"]
  OA["OpenAlice (WSL / VPS)\nagent + inbox + UTA"]
  MT -->|"Bearer AUTH_TOKEN\n/mcp"| OA
  OA -->|"source: alpaca-…"| ALP["Alpaca UTA\nUS equities"]
  OA -->|"source: ibkr-…"| IBK["IBKR UTA\nFX + metals + futures"]
  OA -->|"source: ccxt-…"| CCX["CCXT UTA\ncrypto per exchange"]
  IBK --> GW["IB Gateway / TWS\npaper or live login"]
```

**Rules (unchanged):**

- Broker / trade keys **never** go in market-terminal or Railway.
- Alice calls `getPortfolio` / `placeOrder` on the **correct `source`** for the asset.
- market-terminal `decision_brief` is still the one-call research read; route
  execution to the UTA that actually supports the symbol.

---

## Broker options in OpenAlice

Sources: [OpenAlice README](https://github.com/TraderAlice/OpenAlice) (architecture),
`BROKER_REGISTRY` in upstream `src/domain/trading/brokers/registry.ts` (UI-facing
types), and CCXT’s exchange list (crypto only).

### User-facing brokers (add via OpenAlice **Trading** UI)

These are the broker **types** you can create today. Each becomes a UTA with id
`{type}-{hash}` (e.g. `alpaca-37cbc8aa`, `ibkr-a1b2c3d4`).

| Type | Name | Asset classes | Paper / demo | Auth | Best for |
|------|------|---------------|--------------|------|----------|
| **`ibkr`** | Interactive Brokers | **Forex (IDEALPRO)**, **metals** (XAUUSD, XAGUSD), **futures** (GC, SI), US/global stocks, options, bonds | Separate IBKR paper account + paper TWS/Gateway login | **No API key** — TCP to TWS/Gateway (`127.0.0.1`, port **4002** Gateway paper / **7497** TWS paper) | **Primary path for forex + metals** with one Alice loop |
| **`alpaca`** | Alpaca | US equities, ETFs; some crypto pairs | Free paper (`PK…` keys → `paper-api`) | REST API key + secret | US stock ideas from `daily_hitlist` / `trade_setup` |
| **`ccxt`** | CCXT (per exchange) | **Crypto only** on 100+ CEXs (Binance, Bybit, OKX, Coinbase, Kraken, …) | `sandbox` / `demoTrading` flags per exchange | Per-exchange API keys (trade-only, **no withdrawal**) | Crypto execution; **not** spot forex |

**CCXT is not a forex broker.** It unifies **cryptocurrency exchanges**. Traditional
FX (EURUSD as a currency pair) requires **IBKR** (or a platform outside OpenAlice —
see below).

### Mentioned in OpenAlice architecture (not in the public UI registry yet)

| Component | Role |
|-----------|------|
| **Longbridge** | Native SDK dep in the UTA carrier image (HK/US-oriented broker). Listed in upstream README next to Alpaca/IBKR/CCXT; **not** in `BROKER_REGISTRY` as of early 2026 — treat as upstream/in-progress unless your OpenAlice build exposes it in **Trading → Add account**. |
| **MockBroker** | In-memory dev/tests only — not for real or paper trading. |

### Not available inside OpenAlice today

These are common for manual forex/metals trading but have **no OpenAlice UTA adapter**:

| Platform / broker | Typical use | Integration path |
|-------------------|-------------|------------------|
| **MetaTrader 4 / 5** | FX + CFD metals | **Manual** execution (SPEC-allowed). Research from market-terminal; you click MT5. Optional bridges (e.g. MetaAPI) are **not** shipped in OpenAlice. |
| **NinjaTrader** | Futures / metals | **Manual** or separate automation (SPEC-allowed). |
| **OANDA**, **IG**, **FXCM**, **cTrader** brokers | FX CFD | No native OpenAlice broker — would need custom UTA or manual. |
| **Alpaca** | — | No forex, no COMEX metals. |

---

## Recommendation for forex + metals

| Goal | Broker UTA | Example symbols |
|------|------------|-----------------|
| **Major FX pairs** | **IBKR** | `EUR.USD`, `GBP.USD`, `USD.JPY`, `USD.CHF`, `AUD.USD` |
| **Gold (spot)** | **IBKR** | `XAU.USD` (IDEALPRO) |
| **Gold (futures)** | **IBKR** | `GC` (COMEX) — aligns with terminal **COT** on `GC=F` |
| **Silver** | **IBKR** | `XAG.USD` or `SI` futures |
| US equity swing / day | Alpaca (optional second UTA) | `NVDA`, `QQQ`, … |
| Crypto | CCXT or Alpaca | `BTC/USD` etc. |

**Default split:** **IBKR UTA = primary book** (forex + metals). Keep **Alpaca**
only if you still want US equity paper on the side.

---

## Setup — IBKR paper (forex + metals)

### 1. IBKR account

1. Open / get approved for an IBKR account (paper is enabled from Client Portal
   after approval — see [IBKR paper trading lesson](https://www.interactivebrokers.com/campus/trading-lessons/request-paper-trading-account/)).
2. Client Portal → **Settings → Paper Trading Account** → separate paper login.
3. Enable **Forex** and **US futures** permissions on the paper account if offered.

### 2. IB Gateway (recommended) on Windows

1. Install **IB Gateway** (lighter than full TWS).
2. Log in with **paper** credentials; select paper trading mode.
3. **Configure → Settings → API → Settings:**
   - Enable **ActiveX and Socket Clients**
   - Socket port: **4002** (Gateway paper) or **7497** (TWS paper)
   - Trusted IPs: `127.0.0.1` and your WSL host IP if OpenAlice runs in WSL

### 3. OpenAlice account (Web UI)

**Trading → Add account → IBKR**

| Field | Typical value |
|-------|----------------|
| Host | `127.0.0.1` or Windows host IP from WSL |
| Port | `4002` (Gateway paper) |
| Client ID | `1` (unique per API connection) |
| Account ID | Paper code e.g. `DU1234567` (optional; auto-detect if omitted) |

Confirm in `pnpm dev` log: `IbkrBroker[ibkr-…]: connected`.

`accounts.json` is sealed — prefer the UI over hand-editing.

### 4. Guards (stop / TP discipline)

Per IBKR UTA in OpenAlice:

- **Symbol whitelist:** `EUR.USD`, `XAU.USD`, `GC`, …
- **Max position size** per instrument
- **Cooldown** between orders

Prompt rule: every entry uses a **bracket** (entry + stop + take-profit). After
fill, verify open orders on **`source: ibkr-…`** before opening the next trade.

---

## Research registry (market-terminal)

`decision_brief` **auto-registers equities** for vol/news; **forex and futures do not**.

Pre-seed your universe (MCP or Registry UI):

```
instruments_add asset=forex symbol=EURUSD
instruments_add asset=forex symbol=USDJPY
instruments_add asset=forex symbol=USDCHF
instruments_add asset=forex symbol=USDCAD
instruments_add asset=forex symbol=XAUUSD
instruments_add asset=futures symbol=GC=F
```

Then call `decision_brief` with registry ids where needed, e.g. `forex:EURUSD`.

### Symbol map (research ↔ IBKR)

| market-terminal | IBKR (typical) | Notes |
|-----------------|----------------|-------|
| `EURUSD` / `forex:EURUSD` | `EUR.USD` | IDEALPRO uses dotted pairs |
| `XAUUSD` | `XAU.USD` | Spot gold |
| `GC=F` / `futures:GC=F` | `GC` front future | COT in terminal is on GC; thesis can reference COT while executing XAU or GC |

Alice resolves IBKR contracts via its own search tools; when in doubt, name both
the **research symbol** and the **IBKR contract** in trade cards.

---

## Prompt patterns

### Portfolio — always pass `source`

```text
getPortfolio + getAccount  source: ibkr-<your-id>     # FX + metals book
getPortfolio + getAccount  source: alpaca-37cbc8aa   # US equities (optional)
```

Without `source`, multi-UTA setups often return `Account temporarily unavailable`.

### Route execution by asset

| Idea from research | Execute on |
|--------------------|------------|
| `decision_brief` / `forex_brain_*` on `EURUSD` | `source: ibkr-…` |
| `decision_brief` on `GC=F` / gold thesis | `source: ibkr-…` (`XAU.USD` or `GC`) |
| `trade_setup` / `daily_hitlist` equity | `source: alpaca-…` |
| `crypto_brain_*` | `source: ccxt-…` or Alpaca if pair exists |

### Persona snippet (add to `data/brain/persona.md`)

```markdown
## Multi-broker execution

- Forex and metals: execute only on IBKR UTA (`source: ibkr-…`).
- US equities: Alpaca UTA (`source: alpaca-…`) when used.
- Never call placeOrder without an explicit human APPROVE in chat or inbox.
- Every entry: bracket with stop + take-profit; after fill, verify open orders on the same source.
- Research: market-terminal `decision_brief` first; label EOD vs live quote time.
```

---

## Smoke tests

### IBKR connectivity (WSL, while Gateway runs on Windows)

```bash
node <<'SCRIPT'
const MCP = "http://127.0.0.1:47332/mcp";
const SOURCE = "ibkr-REPLACE_ME";
async function rpc(name, args = {}) {
  const res = await fetch(MCP, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json, text/event-stream" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name, arguments: args } }),
  });
  const text = await res.text();
  const jsonText = text.includes("data:") ? text.split("\n").filter(l => l.startsWith("data:")).map(l => l.slice(5).trim()).pop() : text;
  const t = JSON.parse(jsonText).result?.content?.[0]?.text;
  console.log(name + ":", t);
}
(async () => {
  await rpc("getPortfolio", { source: SOURCE });
  await rpc("getAccount", { source: SOURCE });
})();
SCRIPT
```

### Research + routing (shell workspace)

```bash
agent -f -p "Call analysis_regime once. decision_brief for EURUSD and XAUUSD (sequential, 2s pause). List trading accounts and getPortfolio for ibkr source only. No orders."
```

---

## A9 cloud note

On a VPS, **IB Gateway must run where OpenAlice can reach it** (same host or VPN).
Alpaca-only cloud deploy is simpler (REST, no local socket). Forex/metals on A9
implies: Gateway + OpenAlice on the VPS, or Gateway on a home PC with a secure
tunnel — document your choice before go-live. See [`openalice-cloud-deploy.md`](openalice-cloud-deploy.md).

---

## CCXT exchange examples (crypto UTA only)

OpenAlice loads the exchange list from the installed `ccxt` package (**100+** names).
Common choices (verify in **Trading → CCXT → exchange** dropdown):

| Exchange id | Notes |
|-------------|-------|
| `binance` | Large liquidity; geo restrictions apply |
| `bybit` | Perps + spot; demo trading flag |
| `okx` | Passphrase often required |
| `coinbase` | US-friendly |
| `kraken` | Spot + futures via `krakenfutures` |

Use **trade-only** API keys; disable withdrawals. For your stated priority (forex +
metals), treat CCXT as **optional** alongside IBKR.

---

## Summary

| Need | Use |
|------|-----|
| Forex + metals in one Alice loop | **IBKR UTA** + IB Gateway paper |
| US stocks paper | **Alpaca UTA** (optional) |
| Crypto | **CCXT UTA** or Alpaca |
| MT5 / OANDA / NinjaTrader | **Outside OpenAlice** — research here, execute there |

market-terminal already researches forex and metals; the gap is **execution UTA**,
not research features.
