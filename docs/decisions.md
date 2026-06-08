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

### E.6 — Hourly FX test: also no lift
Tested Kronos on **hourly** FX (its native cadence). Limitation: yfinance only
returns ~1 month of hourly (500 bars) — too shallow for a deep context. On that
thin data, EURUSD hourly directional was **~47% (below coin)** — *worse* than
daily's 60%, not better. Frequency was not the unlock (within free-data limits).

### E.7 — DECISION: pivot the forecasting pillar to VOLATILITY
After a thorough sweep (daily futures dead; daily crypto weak; daily FX a modest,
uneven ~55% lean with broken bands; hourly no lift) and independent evidence that
**no open model beats persistence on daily price**, we **pivot the forecasting
pillar from price/direction to volatility** — the one place these methods have
proven, defensible skill.
- **Method:** **HAR-RV** (Corsi 2009) — the academic workhorse for realized-vol
  forecasting — plus EWMA & persistence baselines and a vol-**regime** read
  (percentile of current vol vs its own history: calm/normal/elevated/stressed).
- **Why it fits:** pure numpy, **no torch, no HuggingFace, no separate service** —
  so it ships **in-core** (like the analysis layer), reversing the E.0 "separate
  service" decision (that was only needed for the heavy Kronos model). Framed as
  interpreted research context (regime/sizing), never a trigger.
- **Built & validated in-sandbox:** `vol/` (realized estimators, HAR-RV, EWMA,
  regime) with unit tests on synthetic data — no "run it on your machine" loop.
- **Kronos:** the price/direction chase is **closed**. The modest daily-FX
  directional lean (~55%) may later return as an *optional, disclaimed secondary*
  signal, but it is not the pillar.

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
