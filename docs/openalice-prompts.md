# OpenAlice — daily trading prompts (research → execute loop)

Three copy-paste prompts for the **Alpaca + IBKR paper** stack: **monitor** open
trades, **scan** for new ideas, and **reconcile** at end of day. They encode the
hard-won rules from [`openalice-daily-runbook.md`](openalice-daily-runbook.md) and
[`openalice-multi-broker.md`](openalice-multi-broker.md):

- **Source ids** — equities `alpaca-1c173aa4`, forex/metals `ibkr-tws-b3ca59a7`.
  Route every order by asset; always pass `source` (multi-UTA `getPortfolio`
  without it returns the wrong account / "temporarily unavailable").
- **GTC protective legs** — every held position's stop **and** take-profit must be
  `TIF=GTC`, never DAY (DAY legs die at the session close → naked overnight).
  Verify on the venue after fill, not just via `getOrders`.
- **Conflict gate** — `decision_brief` returns a `conflict` block; size HARDER
  against it and **drop** `fundamental_conflict` / `news_conflict`.
- **Execution naming** — `decision_brief` also returns an `execution` block with
  the IBKR contract (`EURUSD → EUR.USD`, `XAUUSD → XAU.USD`, `GC=F → GC`); name
  both the research symbol and the IBKR contract in trade cards.
- **Risk** — ≤1% account risk per trade; stop ≥1.5× daily σ from current price.
- **Hours (UTC)** — US equities Mon–Fri 13:30–20:00; forex/metals (IDEALPRO)
  ~Sun 22:00 → Fri 22:00.
- **Nothing executes without an explicit human `APPROVE`.**

> First run on a fresh registry: have Alice call `ensure-book` (MCP
> `instruments_add` or `POST /instruments/ensure-book`) so the forex+metals
> universe (`forex:EURUSD` … `forex:XAUUSD`) is tracked before deep dives.

---

## Prompt 1 — Monitor open trades & report

```
Role: You are managing the Alpaca + IBKR PAPER accounts. The market-terminal MCP
server is your research brain — it does not place orders, you do. This is a
monitoring + reporting pass only: do NOT open, close, or modify anything.

1. Pull open positions + working orders from BOTH books, passing source:
   - getPortfolio + getAccount source: alpaca-1c173aa4    (US equities)
   - getPortfolio + getAccount source: ibkr-tws-b3ca59a7  (forex + metals)
   For each: symbol, side, qty, avg entry, current price, unrealized P/L, %equity.

2. Refresh the thesis for each position from the terminal:
   - decision_brief(symbol, asset) → conviction, setup, news_pulse, vol, macro,
     the `conflict` block, and the `execution` block (IBKR contract).
   - news_pulse(symbol, asset) → last-24h headlines + 24h directional lean.
   - Stocks: also check sec_filings(ticker) for new 8-K / Form 4.

3. Classify each position:
   - INTACT      — brief supports the side; conflict = aligned.
   - WEAKENING   — momentum fading, vol regime stressed/elevated, or news_pulse
                   now neutral/against.
   - BROKEN/FLIP — conflict is fundamental_conflict/news_conflict against my side,
                   or a material new filing/news invalidates the entry.

4. PROTECTION AUDIT (critical): for every position confirm a live GTC stop AND a
   live GTC take-profit on its own source. Check TIF=GTC on the venue, not just
   getOrders (which may show only the parent leg). Flag any position whose legs
   are DAY, missing, or whose stop now sits too close (< ~1.5× daily σ from price).

5. Risk check: distance to stop, %equity, and whether vol expansion means the
   size is now too large for the regime.

Send ONE concise update:
  • Table: symbol | source | side | %equity | unrealized P/L | thesis | conflict |
    GTC stop? | GTC TP? | one-line reason.
  • "Needs attention": only WEAKENING/BROKEN names + a specific RECOMMENDATION
    (trim / tighten / exit / re-arm GTC leg).
  • "Protection gaps": any position missing a GTC stop or TP — highest priority.
  • Label data freshness (terminal stamps each section's as-of date).

Do NOT execute. End with: "Reply 'go' to act on any of these."
```

---

## Prompt 2 — Scan for new opportunities

```
Role: Hunt for new PAPER trade ideas across the Alpaca (US equities) and IBKR
(forex + metals) books. market-terminal is the research brain. Propose ideas —
do not execute without my "go".

Discipline (decision_brief returns a `conflict` block — size HARDER against it):
  - aligned            → full candidate, normal size.
  - momentum_only      → half size at most; needs a clean confirmed trigger.
  - fundamental_conflict / news_conflict → DROP. Never trade against the
    fundamentals or 24h news no matter how strong the momentum (the CBRL mistake).

Pipeline:

1. Macro frame: analysis_regime (risk-on/off).

2. Cast a wide net, respecting market hours:
   - Equities (if 13:30–20:00 UTC): daily_hitlist(limit=15, min_move_pct=2.0),
     market_movers(top=20), brain_screen().
   - Forex/metals (if ~Sun 22:00→Fri 22:00 UTC): forex_brain_screen() over the
     tracked book (EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, USDCAD, XAUUSD, XAGUSD).
   - Crypto (optional): crypto_brain_screen().

3. Top ~6-8 candidates → full read each:
   - decision_brief(symbol, asset) → package + `conflict` + `execution`.
   - trade_setup(ticker) for stocks / market_setup(asset, symbol) for fx/metals
     → bias, triggers, participation (in-play vs quiet).

4. Conflict gate: reject fundamental_conflict/news_conflict and "quiet" setups.

5. Rank survivors by conviction × trigger cleanliness. For each, a TRADE CARD:
   • research symbol + IBKR/Alpaca contract (from `execution`) + source to route
     (equity → alpaca-1c173aa4, forex/metals → ibkr-tws-b3ca59a7)
   • direction, entry, STOP (≥1.5× daily σ), take-profit
   • size as %equity (≤1% account risk; respect the conflict sizing rule)
   • conflict class + conviction
   • 1-2 sentence thesis + the single biggest risk.

Output: ranked shortlist, best first, max 5 ideas, each ≤5 lines, freshness
labelled. "No clean setups today" is a valid, good answer.

Every entry must be a bracket (entry + GTC stop + GTC take-profit). Do NOT place
orders. End with: "Reply 'go <symbol>' to take any of these on paper."
```

---

## Prompt 3 — End-of-day reconcile

```
Role: END-OF-DAY RECONCILE on the Alpaca + IBKR PAPER accounts. market-terminal is
the research brain. Review + journaling only — do NOT open, close, or modify any
position. Be honest; surface mistakes, don't rationalize them.

1. Pull today's activity from BOTH sources (alpaca-1c173aa4, ibkr-tws-b3ca59a7):
   all fills (entries + exits), open positions, realized + unrealized P/L.

2. For EACH trade opened/closed today, reconstruct decision vs. outcome:
   - Re-pull decision_brief(symbol, asset) + news_pulse — what the research said
     near entry: conviction, `conflict` class, setup trigger, 24h news, vol regime.
   - What happened: direction, size %equity, P/L.
   - Verdict:
       • CLEAN WIN     — aligned brief, thesis played out.
       • CLEAN LOSS    — aligned brief, lost anyway (acceptable variance).
       • PROCESS ERROR — traded INTO a conflict, oversized for the vol regime,
                         chased a quiet setup, ignored a filing, OR left a DAY/
                         missing protective leg. Flag loudly regardless of P/L.
       • LUCKY         — won despite a process error (still a defect to fix).

3. Discipline scorecard:
   - Trades taken vs. trades that cleared the conflict gate.
   - Count of PROCESS ERROR + LUCKY (what to fix — not the losses).
   - Largest single position %equity and total deployed — sizing respected?
   - PROTECTION at close: every held position has a verified GTC stop AND TP on
     its source? List any that don't (these survive the weekend naked).
   - Any open position whose thesis flipped (re-check conflict) for tomorrow.

4. Skill vs. beta: macro_dashboard() + market_movers(top=20) — did my names just
   follow the tape, or did the research add an edge?

Send ONE end-of-day report:
  • Header: realized P/L, open unrealized P/L, # trades, win rate.
  • Per-trade table: symbol | source | %equity | P/L | brief-said (conflict/
    conviction) | verdict.
  • "Process notes": the specific rule(s) broken today + the concrete fix for
    tomorrow (e.g. "halve size when vol regime = stressed", "never enter on
    momentum_only without a confirmed trigger", "re-arm GTC TP before the close").
  • "On watch tomorrow": open positions with weakening/flipped theses.
  • "Weekend protection": confirm every held position is GTC-protected (safe with
    the machine off) or flag the gap.
  • Freshness labels on every section.

Keep it tight and unflattering. Do NOT execute anything.
```

---

## Daily cycle

1. **Opportunities** (Prompt 2) — scan, conflict-gated trade cards → you `go`.
2. **Monitor** (Prompt 1) — position health + protection audit → trim/exit recs.
3. **Reconcile** (Prompt 3) — self-audit; PROCESS ERROR / LUCKY feed tomorrow's
   scan. Confirms weekend GTC protection before you leave the desk.

Persona note: the standing rules (route by source, GTC legs, conflict gate, human
APPROVE) belong in `data/brain/persona.md` on the OpenAlice side so they apply to
every session, not just these prompts. See the persona snippet in
[`openalice-multi-broker.md`](openalice-multi-broker.md).
