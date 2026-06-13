# OpenAlice daily runbook (WSL + IBKR + Alpaca)

Operator checklist for the **execution stack** on the WSL host: cold start after a
reboot, the daily research→execute loop, and what's safe when you leave the desk.

Stack recap:

| Component | Where | Start needed? |
|-----------|-------|---------------|
| **market-terminal** (research MCP) | Railway (remote) | No — always up |
| **OpenAlice** (agent, inbox, UTA) | WSL · `pnpm dev` | **Yes, every boot** |
| **IB Gateway** (forex/metals) | WSL · WSLg GUI | **Yes, every boot + login** |
| **Alpaca / OKX UTAs** | OpenAlice config | Auto on `pnpm dev` |

`source` ids: `alpaca-61b238e3` (equities) · `ibkr-tws-aa6a879b` (forex/metals).

---

## A. Cold start (after reboot or fresh login)

### 1. Launch IB Gateway (WSL)
```bash
~/Jts/ibgateway/*/ibgateway &
```
In the window: **IB API** + **Paper Trading** → enter trial creds → **Paper Log In**.
(API settings persist: port 4002, Read-Only off, localhost-only ok.)

### 2. Verify the Gateway socket
```bash
timeout 2 bash -c "</dev/tcp/127.0.0.1/4002" 2>/dev/null && echo OPEN || echo CLOSED
```
Want **OPEN**. If CLOSED → Gateway isn't logged in yet (finish step 1).

### 3. Start OpenAlice (separate WSL tab)
```bash
cd ~/OpenAlice && pnpm dev
```
Watch for: `AlpacaBroker[alpaca-61b238e3]: connected`, `IbkrBroker[ibkr-tws-…]: connected`, UI on `:5173`.

### 4. Open the UI + verify
- Browser → **http://localhost:5173**, log in (admin token).
- **Trading** page → Alpaca + IBKR both **healthy**.
- Quick feed check in a workspace (no orders):
  ```
  List trading accounts. analysis_regime. getPortfolio source alpaca-61b238e3. No orders.
  ```

If all green, the stack is live.

---

## B. Daily trading workflow

1. **Macro frame** — `analysis_regime` (risk-on/off).
2. **Discovery** — `daily_hitlist`, `brain_screen`, `market_screen` (crypto/forex), `forex_brain_screen`.
3. **Deep dive** — `decision_brief` on top names (sequential, ~2s pause). Read `conflict` + `caution`; drop `fundamental_conflict`/high-caution.
4. **Trade cards** — entry / stop (≥1.5× daily σ) / TP / size (≤1% risk). Route by asset:
   equity → `alpaca-61b238e3`, forex/metals → `ibkr-tws-aa6a879b`.
5. **Approve** — nothing executes without your explicit `APPROVE`.
6. **Execute with a bracket** — entry + stop + TP. **Every protective leg `TIF=GTC`, never DAY** (DAY legs die at the close → naked overnight; see `openalice-multi-broker.md`).
7. **Verify on the venue** — after fill, confirm the stop *and* TP are live with GTC (don't trust `getOrders` alone — it may show only the parent leg).
8. **Report** — positions, stops/TPs, gap report.

Market hours: **US equities** 13:30–20:00 UTC (Mon–Fri). **Forex/metals (IDEALPRO)** ~Sun 22:00 → Fri 22:00 UTC. Outside hours: equity market orders reject (use GTC limits); forex simply closed.

---

## C. Leaving the desk

**Your broker stops protect you even with the machine off.** GTC stop/TP orders
live on **Alpaca's / IBKR's servers**, not on your PC — they trigger regardless of
whether OpenAlice, the Gateway, or the machine is running. So an open position
with a verified GTC stop is safe to leave.

What you lose when the machine/OpenAlice is off: **agent monitoring, inbox, cron,
and any new analysis** — not the protective orders.

### Keep it running while away (machine on)
A backgrounded `&` process dies when its terminal closes. To keep OpenAlice (and
the Gateway) alive with the terminal shut, use **tmux**:
```bash
tmux new -s alice          # then: ~/Jts/ibgateway/*/ibgateway &  and (new pane) pnpm dev
# detach: Ctrl-b then d     reattach later: tmux attach -t alice
```
- Disable Windows/WSL sleep if you want 24/7 monitoring.
- **IB Gateway logs out once a day** by default. In **Configure → Lock and Exit**, set **Auto restart** (not Auto logoff) so it re-auths instead of dropping. (You re-enter creds after IB's weekly server reset.)

### Powering the machine off
Fine to do — just know:
- Open positions stay protected by their **GTC broker stops**. ✅
- No agent monitoring / inbox / cron until you boot back up (cold start = section A).
- For true 24/7 (laptop off), that's **ROADMAP A9** — OpenAlice on an always-on VPS (`openalice-cloud-deploy.md`).

---

## D. Clean shutdown (optional)
1. Ctrl-C the `pnpm dev` tab (or `tmux kill-session -t alice`).
2. Close IB Gateway (File → Exit).
3. Broker GTC orders remain active server-side — nothing to do there.

---

## Quick reference

```bash
# cold start
~/Jts/ibgateway/*/ibgateway &              # then Paper Log In
timeout 2 bash -c "</dev/tcp/127.0.0.1/4002" && echo OPEN
cd ~/OpenAlice && pnpm dev                 # then open http://localhost:5173
```

| Check | Expected |
|-------|----------|
| `127.0.0.1:4002` | OPEN (Gateway up + logged in) |
| UI `:5173` | loads, login works |
| Trading page | alpaca + ibkr healthy |
| Open positions | each has a **GTC** stop + TP on the venue |

See also: `openalice-multi-broker.md` (broker setup + bracket lesson),
`openalice-workflow.md` (research loop), `openalice-cloud-deploy.md` (A9 24/7).
