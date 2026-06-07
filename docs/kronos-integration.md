# Design RFC — Kronos forecasting layer

**Status:** Draft for review · **Roadmap:** §E · **Goal:** add the *forecasting*
pillar toward a Bloomberg-style terminal, isolated and research-framed, without
crossing the execution boundary.

This is a **design-on-paper** document — no code yet. It fixes the architecture,
the rule-compliance framing, and the decisions to confirm before we build (E1→E5).

---

## 1. What Kronos is (and how we'll use it)

[Kronos](https://github.com/shiyu-coder/Kronos) (MIT) is an open-source
foundation model for OHLCV candlesticks. Input: a price history (OHLCV +
timestamps). Output: a **probabilistic forecast** of the next *N* bars — it
samples multiple future paths (via temperature `T` / nucleus `top_p`), which we
reduce to a **median path + quantile band**. Models on HuggingFace: `mini`
(4.1M, ctx 2048), `small` (24.7M, ctx 512), `base` (102.3M, ctx 512). PyTorch.

We use it for one thing: *"given this instrument's recent bars, what's the
model's forecast distribution for the next N bars?"* — surfaced as research
context, never as a recommendation.

## 2. Rule compliance (this is the load-bearing part)

The terminal's hard rules say research only, no trade triggers, execution
delegated. A forecast is the closest thing to a signal we'd ever show, so the
framing matters:

1. **Probabilistic, not a price target.** We always render a **distribution**
   (median + e.g. p10/p25/p75/p90 band), never a single "GC will hit X." That
   keeps it factual ("the model's distribution") rather than a call.
2. **Disclaimed, like the analysis layer.** Every forecast carries a
   forecast-specific disclaimer: *"Model-generated probabilistic forecast —
   research context only, not advice or a trade trigger; forecasts are uncertain
   and frequently wrong."*
3. **Isolated dependency.** A new `kronos_layer/` is the **only** module that
   imports `torch` / Kronos — exactly mirroring the rule that `obb_layer/` is the
   only module that imports `openbb`.
4. **Execution boundary intact.** Alice *pulls* the forecast as one more input
   and decides on her side. The forecast never instructs an action; orders still
   never flow back into this repo.

## 3. Architecture

### 3.1 Layering (mirrors the existing structure)

```
kronos_layer/        the ONLY place that imports torch / Kronos
  client.py          lazy singleton: load tokenizer+model once, cache (like obb_layer.get_obb)
  forecast.py        forecast(ohlcv_df, horizon, samples, T, top_p) -> ForecastResult
  normalize.py       map our OHLCV frame -> Kronos's expected df + timestamps
  types.py           ForecastResult (median path, quantile bands, raw paths, meta)

services/forecast.py assemble instrument OHLCV (via obb_layer) -> kronos_layer ->
                     attach plain-language read + disclaimer -> Envelope (cached)
app/routers/forecast.py   GET /forecast/{instrument}?horizon=...
mcp_server.py        a `forecast` tool; fold a short summary into analysis_brief
web/                 history + forecast-cone chart (lands in the C4 instrument view)
```

### 3.2 Data flow

```
obb_layer (EOD OHLCV)  ->  services/forecast (assemble df, TTL-cache check)
   ->  kronos_layer.forecast (model inference)  ->  ForecastResult
   ->  Envelope  ->  REST / MCP / UI
```

Nothing new touches `obb_layer`; forecasting is a *consumer* of the OHLCV we
already fetch.

### 3.3 The key decision — where inference runs

| | **A. In-app (feature-flagged)** | **B. Separate forecasting service** *(recommended)* |
|---|---|---|
| Shape | torch loaded in the FastAPI process; inference in a threadpool | a 2nd service (own Dockerfile + torch) exposing `POST /forecast`; the terminal calls it over HTTP |
| Core image | bloated (~2–3 GB), +1–2 GB RAM baseline | **stays lean** (no torch in the core) |
| Failure mode | a heavy dep in the research app | terminal degrades gracefully via the existing **circuit breaker** if the forecaster is down |
| Deploy | one service | two Railway services (matches the multi-service future we already planned) |
| Scaling | coupled | independent (GPU later, if ever) |
| Complexity | simplest | one network hop + an internal service token |

**DECIDED: B (separate forecasting service).** Build `kronos_layer/` as a clean
**library**, then wrap it in a thin `forecast_service` (FastAPI) that imports it.
The terminal's `services/forecast.py` calls that service through an HTTP client
guarded by `circuit.py`, with an internal service token. The **same
`kronos_layer/` library** is reused regardless, so if we ever want the in-app
path (A), it's a small wrapper — the decision isn't one-way. For **E1
(evaluate)** we use the library directly, no service needed.

## 4. Config additions (`config.py`)

```
kronos_enabled: bool = False          # master switch; core behaves identically when off
kronos_model: str = "small"           # mini | small | base
kronos_device: str = "cpu"            # cpu | cuda
kronos_service_url: str | None = None # set when using the separate service (B)
kronos_horizon_default: int = 30      # bars to forecast
kronos_samples: int = 30              # sampled paths to reduce to a band
```

Dependencies stay **out of the core**: torch/kronos/huggingface-hub live in the
forecast service's own requirements (B), or in an optional extra imported lazily
inside `kronos_layer.client` (A). Either way the core `requirements.txt` and the
fast CI job are untouched.

## 5. Caching & cost

Inference (sampling N paths) is expensive, so cache per
`(instrument, horizon, model, latest_bar_date)` in the existing `cache/store.py`
with a TTL matched to bar frequency (daily bars → ~1 day). Forecast warming is
**off by default** (too heavy for the pre-cache loop); opt-in later.

## 6. Testing / CI

- `kronos_layer` unit tests run with the **model mocked** (a fake predictor) —
  they assert the normalize/IO and `ForecastResult` shape, **no torch in the
  core CI job**, so CI stays fast.
- The forecast service (B) gets its own optional CI that installs torch and runs
  a tiny smoke forecast.
- The real model never runs in the core pipeline.

## 7. Evaluation plan (E1 — do this first)

A harness (`scripts/eval_kronos.py`, run locally — this repo's sandbox can't
reach HuggingFace):

1. Pull ~512 daily bars of `GC=F` and `NQ=F` via `obb_layer`.
2. **Hold out** the last 30 bars; forecast them from the prior history with
   `Kronos-small`.
3. Score: directional hit-rate, MAE/MAPE vs actual, and **band coverage** (did
   actuals fall in the p10–p90 cone at the stated rate?).
4. Plot history + median + band vs actual.

**Gate:** only proceed to E2+ if daily futures look in-distribution enough to be
useful. Kronos demos on crypto-hourly, so this is a genuine unknown.

## 8. Rollout (maps to roadmap §E)

| Step | Deliverable | Gate |
|---|---|---|
| **E1** | `kronos_layer` library + eval harness | forecasts are useful on our daily bars? |
| **E2** | finalize `kronos_layer` API + mocked tests | clean, typed, cached |
| **E3** | `services/forecast` + `/forecast/{instrument}` + `forecast` MCP tool + fold into `analysis_brief` | research-framed, disclaimed |
| **E4** | history + forecast-cone chart (in the C4 instrument view) | — |
| **E5** | deploy topology (separate service + inter-service auth + circuit breaker) | core stays lean |

## 9. Decisions (locked)

1. **Deploy topology** — ✅ **separate forecasting service** the terminal calls
   over HTTP (§3.3 B). Core stays lean; degrades gracefully via the circuit
   breaker.
2. **Model size for v1** — ✅ start with `small` (fast, cheap eval); move to
   `base` only if E1 shows quality needs it.
3. **Scope** — ✅ daily futures watchlist first (GC, NQ, …), matching our data.
4. **Expose to Alice when?** — ✅ terminal-only until E1 validates, *then* add the
   `forecast` MCP tool so Alice consumes it.
