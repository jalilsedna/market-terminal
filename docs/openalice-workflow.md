# OpenAlice — full research workflow (Cursor + market-terminal)

Step-by-step operator guide for the **research-only paper loop**: market-terminal
MCP → Cursor Agent in an OpenAlice **shell** workspace → `inbox_push` → manual
approval in OpenAlice. No orders from the terminal.

See also: [`openalice.md`](openalice.md), [`openalice-multi-broker.md`](openalice-multi-broker.md)
(forex/metals via IBKR + multi-UTA `source`), [`openalice-cursor-fallback.md`](openalice-cursor-fallback.md).

---

## Where to run

| Surface | Use |
|---------|-----|
| **OpenAlice shell workspace** + `agent -f` | Research workflow, MCP tools, this prompt |
| **OpenAlice Inbox** | Read proposals, reply, approve paper trades |
| **OpenAlice sidebar (Claude)** | Only when Claude Code quota is available |

Workspace: **Chat** template, **MCP** tools, session CLI = **shell**, then `agent -f`.

---

## Persona block (paste into `OpenAlice/data/brain/persona.md`)

```markdown
## Full research workflow (paper only)

When running the daily research workflow:

1. **Never** call placeOrder, modifyOrder, cancelOrder, tradingCommit, or tradingPush.
2. Use **market-terminal** MCP for all research (`decision_brief` first for any symbol idea).
3. Label every number with freshness (EOD date, `as_of`, weekly COT lag, etc.).
4. If a tool errors or returns empty, name the tool and read `skipped` / `errors` — never fabricate.
5. **inbox_push — once per workflow, clean summary only:**
   - Title line: symbol + direction + "paper / manual approval"
   - 2-sentence thesis grounded in `decision_brief` sections
   - Entry / stop / target + position size (≤1% risk on paper equity)
   - Top 2 risks from the brief
   - One line: "NOT executed — awaiting approval"
6. **Do NOT** push script output, gap reports, debug logs, or the full phase-by-phase write-up to the inbox.
```

---

## Workflow prompt (copy into `agent -f`)

Use this in the **shell workspace terminal** after Railway deploy is current.

```
FULL WORKFLOW TEST — research → reasoning only. Paper account. Do NOT call placeOrder/modifyOrder/cancelOrder/tradingCommit/tradingPush under any circumstances. Every idea goes to the inbox for my manual approval. Label every number with its freshness; if a tool errors or returns empty, name the tool and read `skipped` and `errors` — never fabricate a missing read.

Phase 0 — Tool check. List market-terminal MCP tools. Confirm: decision_brief, trade_setup, daily_hitlist, market_setup, market_screen, brain_screen, crypto_brain_screen, forex_brain_screen, analysis_regime. If any missing, stop.

Phase 1 — Macro frame (once). Call analysis_regime. Report regime + score and all contributing signals (including S&P 500 1w if present).

Phase 2 — Cross-asset discovery:
- daily_hitlist → top 5 by confluence
- brain_screen("AAPL,MSFT,NVDA,AMD,GOOGL")
- market_screen asset=crypto
- market_screen asset=forex
Rank the 3 most interesting names across asset classes (one line each why).

Phase 3 — For each of the 3 names, call decision_brief(symbol). Report synthesis verbatim, section summaries, `errors` and `skipped` verbatim, and conviction vs setup vs macro conflict.

Phase 4 — getPortfolio and getAccount with source alpaca-37cbc8aa (see your UTA boot log for the id if it differs). If unavailable, say so and use my stated ~45 QQQ. For each idea: concentrates or diversifies?

Phase 5 — Best idea or "no clean trade". Vol-aware stop (≥1.5× daily σ). Size ≤1% of $100k paper risk. **inbox_push once** with ONLY the short proposal (≤15 lines) — no gap report, no scripts.

Phase 6 — Gap report in chat only (not inbox). List every tool: data / error / skipped.
```

---

## D — Re-run checklist (after fixes or when portfolio is back)

Run in the **same shell workspace** (`agent -f`).

### Pre-flight

```bash
agent status
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "Authorization: Bearer $TOKEN" \
  https://market-terminal-production-131c.up.railway.app/health
```

Expect `200` on `/health`.

### Smoke tests (2 minutes)

```bash
agent -f -p "Call analysis_regime. List all signals — is S&P 500 (1w) present with a real % (not nan)?"

agent -f -p "Call decision_brief for CBRL — show skipped and errors verbatim."

agent -f -p "Call decision_brief for BTC-USD — show news section or skipped.news."
```

| Check | Pass |
|-------|------|
| S&P 500 (1w) | Real % or explicitly absent with reason |
| CBRL `skipped` | vol/news registry message when not tracked |
| BTC news | Headlines or `skipped.news` with reason |
| getPortfolio | Positions with `source: alpaca-…` (see below), or transient error named |

### Full workflow

Paste the **workflow prompt** above. Verify:

- [ ] No trade tools called
- [ ] Inbox has **one** short NVDA (or best-idea) proposal — not the full transcript
- [ ] Phase 6 gap report stayed in **chat only**

### Portfolio tools — always pass `source`

OpenAlice may have several UTA accounts (Alpaca paper, **IBKR** for forex/metals,
CCXT crypto, geo-blocked read-only feeds). **Without `source`, `getPortfolio`
often returns** `Account temporarily unavailable` even when a broker is healthy.

Find each account id in the `pnpm dev` log, e.g.
`AlpacaBroker[alpaca-37cbc8aa]: connected`, `IbkrBroker[ibkr-…]: connected`.
Route FX/metal execution to **IBKR** — see [`openalice-multi-broker.md`](openalice-multi-broker.md).

**Smoke test** (any WSL tab while `pnpm dev` runs):

```bash
node <<'SCRIPT'
const MCP = "http://127.0.0.1:47332/mcp";
const SOURCE = "alpaca-37cbc8aa";
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
(async () => { await rpc("getPortfolio", { source: SOURCE }); await rpc("getAccount", { source: SOURCE }); })();
SCRIPT
```

### When getPortfolio was down

Re-run **Phase 4 only** after OpenAlice UTA / Alpaca paper is healthy:

```bash
agent -f -p "Call getPortfolio and getAccount with source alpaca-37cbc8aa. Re-score NVDA vs my live QQQ exposure using the last workflow thesis. inbox_push only if the portfolio-fit conclusion changed."
```

### Registry tip (hitlist names)

`daily_hitlist` and `decision_brief` for equities/ETFs **auto-register** movers
so vol + news run without a manual `instruments_add`. To pre-track a name:

```
instruments_add asset=equity symbol=CBRL
```

Re-check CBRL after deploy:

```bash
agent -f -p "Call decision_brief for CBRL — show skipped and errors verbatim."
```

Expect vol + news sections (or `skipped.news` only when the wire is empty).
