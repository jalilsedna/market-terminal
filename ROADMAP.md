# ROADMAP

Tracked backlog for the terminal. **Shipped** = done and merged; **Open** =
deferred, worked around, or flagged. See `SPEC.md` for the product spec and
`docs/openalice.md` for the execution-agent integration.

## ✅ Shipped
- Phase 0 — scaffold, capability probe (`obb_layer/probe.py`), TTL cache.
- Phase 1 — V1 Macro Dashboard, V2 Watchlist, V4 COT/Positioning.
- Phase 2 — V3 News Feed, V5 Term Structure (VIX), V6 Sector Rotation.
- Phase 3 — single-page frontend, pre-cache warmer, per-call circuit breaker,
  MCP server (`mcp_server.py`), Execution tab framing OpenAlice.
- OpenAlice wired as a separate execution app: embedded in the Execution tab,
  running from source under WSL2, agent spawns and replies.

---

## A. Finish the OpenAlice integration (active thread)
- [ ] **A1 — Research feed.** Wire market-terminal's MCP into Alice's agent via
      the workspace `.mcp.json`. Decision pending: run market-terminal *in WSL*
      (both apps share localhost) vs. bridge *WSL → Windows* over the network
      (`MCP_HOST=0.0.0.0` + Windows host IP, possible firewall rule). ← next up
- [ ] **A2 — Make the feed durable.** OpenAlice regenerates each workspace's
      `.mcp.json`, so a one-off edit is wiped. Add `market-terminal` to the
      template/seed so every new workspace gets it. (Update `docs/openalice.md`.)
- [ ] **A3 — Verify end-to-end.** Confirm Alice's agent actually calls a
      market-terminal tool (e.g. gold COT) and returns real data.
- [ ] **A4 — Paper account (MockBroker).** UTA shows 0 accounts; set up a
      `type: "mock"` account so Alice can "execute" on paper (no real money).
- [ ] **A5 — Document the OpenAlice-on-WSL setup** (WSL2 + Git-Bash-free,
      `build-essential`, 60s UTA timeout, `claude` login) so it's reproducible.
      Note the 60s timeout edit lives only in their OpenAlice clone.
- [ ] **A6 — Resolve Claude Code's `/doctor` "MCP" warning** in the WSL agent.
- [ ] **A7 — Rotate the OpenAlice admin token.**

## B. Data / provider gaps (documented, still open)
- [ ] **B1 — Economic calendar.** Paywalled on FMP free tier; V1's calendar
      panel is degraded. Needs a paid provider or alternative source.
- [ ] **B2 — World news.** FMP free is paywalled; worked around with
      per-instrument yfinance. Functional but not true world news.
- [ ] **B3 — GC/CL/NG futures curves (V5).** yfinance 401s; only VIX works.
      Needs another source for commodity term structure.
- [ ] **B4 — Provider reliability.** yfinance throttles/401s often; evaluate a
      sturdier EOD provider for the whole terminal.

## C. Skeleton → product
- [ ] **C1 — Tests + CI.** No automated tests today; wire the Phase-0 probe into
      CI so an OpenBB bump can't silently break a view.
- [ ] **C2 — Persistence.** Cache is in-memory and resets on restart; add a
      disk/SQLite layer + history.
- [ ] **C3 — Analysis layer (the edge).** COT extremes vs 1y/3y percentiles with
      signals, curve-flip detection, "what's moving my contracts today." Move
      from *displaying* data to *interpreting* it.
- [ ] **C4 — Cross-view "instrument focus."** One symbol → its COT + price +
      term structure + news on one screen.
- [ ] **C5 — Interactive frontend.** Editable watchlist, charts, alerts
      (e.g. COT extreme / curve flip).

## D. Housekeeping
- [ ] **D1 — Keep `CLAUDE.md` ↔ the Claude Project's custom instructions in
      sync** (rule #1 reframed: execution delegated, not forbidden).

---

**Suggested order:** A1 → A3 (feed working) → A4 (paper account) → A2 (durable),
then choose between **B** (make the data trustworthy) and **C3** (build the
analysis edge — highest long-term value).
