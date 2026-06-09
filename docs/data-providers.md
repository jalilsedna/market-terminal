# Data providers & reliability (ROADMAP B)

The terminal runs on **free providers by default** (yfinance, FRED, CFTC). That's
great for zero-setup, but yfinance **throttles and 401s** under load — the weak
link behind every view, the volatility pillar, and Alice's feed.

## B4 — EOD provider fallback (shipped)

The equity/ETF EOD fetchers try a configurable **provider chain** until one
returns data, so a flaky provider falls back instead of degrading the panel:

```
EOD_PROVIDERS=tiingo,yfinance
```

- Applies to the **equity** and **ETF** routes — including the **sector-rotation
  view** (11 SPDR ETFs, a throttle hotspot) and custom equity/ETF instruments —
  because their symbols (`AAPL`, `SPY`, `XLK`) are **portable across providers**.
- **Safe by default:** the default chain is `yfinance` (unchanged behaviour).
  Adding providers only *adds* resilience; the chain skips a provider that errors
  or returns empty and uses the first that works.
- `/health` reports the active `eod_providers` chain.
- **Verify it's really serving** (a fallback chain fails *silently* — a bad key
  just falls through to yfinance): `python -m scripts.probe_providers` hits each
  provider individually for AAPL and tells you which one the chain serves from.

### Get a free, sturdier provider
- **Tiingo** — free tier, far steadier than yfinance for equities/ETFs. Sign up
  at <https://www.tiingo.com>, then set `TIINGO_API_KEY=...`.
  (`obb_layer/client.py` pushes the key into OpenBB's `tiingo_token` credential.)
- **Polygon / Massive** — **Polygon.io rebranded to Massive.com (2025-10-30)**; a
  `massive.com` key **is** a Polygon key and authenticates OpenBB's `polygon`
  provider unchanged (the legacy `api.polygon.io` endpoint still accepts it). Set
  `POLYGON_API_KEY=...` (`obb_layer/client.py` pushes it into the `polygon_api_key`
  credential). Covers stocks/options/forex/crypto/indices/CME futures.
- **FMP** — another alternative; add the key and place the provider in the chain.

**Recommended chain with both keys:** `EOD_PROVIDERS=tiingo,polygon,yfinance`
(Tiingo primary — most generous free rate; Polygon strong secondary; yfinance the
last-resort free fallback). Verify which one actually serves with
`python -m scripts.probe_providers`.

### Not yet in the chain (why)
- **Crypto / FX / futures** stay on yfinance — providers use **different symbol
  formats** (yfinance `BTC-USD` / `EURUSD` / `GC=F` vs Polygon `X:BTCUSD` /
  `C:EURUSD` / …), so a naive fallback would send the wrong symbol. A per-provider
  **symbol-mapping layer** is the follow-up that unlocks the chain for these
  (B-next) — and Polygon, which covers all of them, becomes the natural backstop
  once that lands.

## Flat Files — whole-market bulk history (Movers screener)

Massive (ex-Polygon) also offers **Flat Files**: an S3-compatible bucket of
compressed daily CSVs where **one ~300 KB `day_aggs_v1` file = every US stock's
OHLCV for that day**. That makes a whole-market scan one cheap download instead
of thousands of REST calls — the basis for the **Movers** tab (top
gainers/losers/most-active across the entire market).

- **Separate S3 credentials** from the REST key — an Access Key ID + Secret from
  the Massive dashboard. Set `MASSIVE_S3_ACCESS_KEY` / `MASSIVE_S3_SECRET_KEY`
  (endpoint `https://files.massive.com`, bucket `flatfiles` are the defaults).
- OpenBB's `polygon` provider is REST-only, so this lives in
  `obb_layer/flatfiles.py` (an S3 client via `boto3`) — the sanctioned
  "OpenBB lacks it → extend here" path. Compute is in `services/movers.py`.
- **Gated:** with the keys unset, the Movers tab/endpoint degrades cleanly and
  `/health` reports `flatfiles_configured:false`. Data is T+1 (each session lands
  ~11:00 AM ET next day). Verify access: `aws s3 ls
  s3://flatfiles/us_stocks_sip/day_aggs_v1/ --endpoint-url https://files.massive.com`.

## Still open (B1–B3)
- **B1 — Economic calendar:** paywalled on FMP free; V1's calendar is degraded.
- **B2 — World news:** FMP free paywalled; worked around with per-instrument
  yfinance news.
- **B3 — Commodity term-structure curves (GC/CL/NG):** yfinance 401s; only VIX
  works. Needs a futures-curve source.
