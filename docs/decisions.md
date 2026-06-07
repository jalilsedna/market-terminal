# Decision log

A durable record of the **decisions and findings** behind this project — so the
reasoning survives container resets and new sessions instead of living only in
chat. Newest first. See `ROADMAP.md` for the task backlog and `SPEC.md` for the
product spec.

---

## E. Forecasting investigation (Kronos) — the evidence

### E.0 — Why a forecasting pillar
The terminal *displays* (views) and *interprets* (analysis layer) data; the
missing third pillar toward a Bloomberg-style terminal is *forecasting*. We
evaluated [Kronos](https://github.com/shiyu-coder/Kronos) (MIT), an open-source
foundation model for OHLCV candlesticks. **Framing rule:** any forecast is shown
as a *probabilistic distribution with a disclaimer* — research context, never a
trade trigger — and `kronos_layer/` is the only module importing torch.

### E.1 — Evaluation method (the bar we hold forecasts to)
`scripts/eval_kronos.py` does **walk-forward** scoring (many non-overlapping
windows, not one slice) against a **persistence baseline** (predict last close,
flat). Three questions decide the gate: beats coin/always-up on **direction**;
beats persistence on **error (MAPE)**; **band calibrated** (~80% p10–p90 cover).
A low MAPE alone is meaningless — on a flat series, persistence wins it for free.

### E.2 — Result: daily FUTURES — FAILED
GC/NQ walk-forward: directional hit ~47% (below coin and the always-up
baseline), MAPE **4–6× worse than persistence**, band coverage 4–11% (vs ~80%).
Counter-intuitively, **more context made it worse** (512-bar daily ≈ 2 years is
far outside Kronos's training distribution). **Conclusion: Kronos has no skill on
daily futures price/direction.** Don't ship it there.

### E.3 — Independent evidence (GitHub deep-search)
A literature/repo survey confirmed this is the *rule*, not a Kronos defect:
- **Rahimikia, [arXiv:2511.18578](https://arxiv.org/abs/2511.18578)** (Nov 2025),
  large leakage-aware study: off-the-shelf time-series foundation models
  (**Chronos, TimesFM, Moirai**) perform **poorly on daily financial returns,
  zero-shot AND fine-tuned**. Gradient-boosted trees (LightGBM/CatBoost) beat
  them. **No open model reliably beats persistence on daily futures
  price/direction.**
- The one robust financial use of these models is **volatility**, not price:
  TimesFM fine-tuned beats GARCH/HAR on realized vol
  ([arXiv:2505.11163](https://arxiv.org/abs/2505.11163)).
- Leads worth a skeptical test: **FinCast**
  ([repo](https://github.com/vincent05r/FinCast-fts)) — the only model trained on
  futures, but evidence is author-reported MSE-on-price only, unverified;
  **TimesFM** ([repo](https://github.com/google-research/timesfm)) — for vol;
  **Qlib + tree ensembles** — the more defensible path for daily.

### E.4 — Result: daily CRYPTO/FOREX — a modest, real FX directional edge
Tested Kronos on its native-ish domains (crypto/forex, daily). Directional hit
vs always-up baseline, 12 windows each:
| | dir hit | always-up | edge? |
|---|---|---|---|
| BTC-USD | 49.2% | 48.3% | no |
| ETH-USD | 54.2% | 50.0% | marginal |
| USDCAD | 64.2% | 58.3% | ✅ |
| EURUSD | 60.0% | 40.8% | ✅ |
| GBPUSD | 58.3% | 45.0% | ✅ |
| NZDUSD | 52.5% | 45.8% | ✅ |
| USDJPY | 47.5% | 60.8% | no |
| AUDUSD | 47.5% | 54.2% | no |

**FX average: Kronos ~55% vs always-up ~51% vs coin 50%.** 4 of 6 majors beat the
baseline — a **real but modest and uneven directional edge**. But: still **no
level/price skill** (loses MAPE everywhere bar NZDUSD) and **bands are broken**
(too narrow, 7–38% coverage — overconfident). It's a *directional lean* signal at
best, in the same category as the COT/regime reads — never a price target.

### E.5 — Model size is not the bottleneck
Kronos-base (102M) is the largest **open** variant; large (499M) is unreleased,
no v2 exists. Bigger models don't fix daily price/direction (Rahimikia tested
larger ones). ~55% FX is near the ceiling for this model class on daily bars.

### E.6 — Decisions
- **DECIDED:** forecasting (if shipped) runs as a **separate service** the
  terminal calls over HTTP (circuit-breaker guarded) — keeps torch out of the
  lean core; matches the multi-service Railway future.
- **DECIDED:** model = **Kronos-base**; daily futures price forecasting is
  **dropped**.
- **OPEN (in progress):** before any fine-tune, test Kronos **zero-shot on
  *hourly* FX** — its proven frequency (the 58–65% directional numbers are
  hourly), and the data volume daily FX lacks. Harness now supports
  `--interval 1h`. Gate: if hourly jumps toward 60–65%, ship/extend; if it's
  also ~55%, pivot the forecasting pillar to **volatility** (the proven win) or
  shelve. (Fine-tuning daily FX was deprioritized: too little data — ~6 pairs ×
  ~2k bars overfits a 102M model — and the evidence says fine-tuned daily still
  fails.)

---

## A–D. Platform decisions (condensed)

- **Architecture.** Built *on* OpenBB consumed as a library (never forked).
  Strict layering: `obb_layer/` is the only place importing `openbb`;
  `kronos_layer/` the only place importing `torch`. Caching + circuit breaker
  in front of every provider call.
- **Execution boundary.** Execution is **delegated, not duplicated** — a separate
  app (OpenAlice) *pulls* research over MCP and trades on its own side. No order
  entry, position state, or broker/trade/withdrawal keys ever live in this repo.
  Proven end-to-end on an Alpaca **paper** account.
- **Deploy (A8).** One Railway service serves the web UI + REST + the MCP feed
  (mounted at `/mcp`) behind a single **auth gate** (`app/auth.py`): a
  login-page session cookie for the browser + a Bearer token for Alice/MCP/API,
  on a `Users` abstraction shaped to become a DB-backed store + registration
  (roadmap F). Live, authenticated, verified.
- **Tests/CI (C1).** pytest (auth, settings, MCP mount, forecast metrics) +
  GitHub Actions: a fast lint+test job and a full-stack import-smoke job so an
  OpenBB bump can't silently break a view. ruff-clean tree.
- **Data caveat (B).** Forecasts (and views) are only as good as the input bars;
  yfinance throttles, daily history is shallow (~1y default / ~2y intraday cap),
  and commodity curves 401. Trustworthy data (roadmap B) gates trustworthy
  forecasts.
