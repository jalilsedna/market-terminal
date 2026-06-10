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

### Crypto / FX in the chain (B-next — shipped)
Crypto and FX now use the **same** fallback chain as equity/ETF, via a
per-provider **symbol-mapping layer** (`obb_layer/symbol_map.py`) that rewrites
our canonical symbol for each provider — e.g. `BTC-USD` → Polygon `X:BTCUSD`,
Tiingo `btcusd`; `EURUSD` → Polygon `C:EURUSD`. A provider with no mapping is
skipped, so the chain still ends on yfinance. Pure + unit-tested
(`tests/test_symbol_map.py`).

### Still yfinance-only (why)
- **Futures** stay on yfinance — continuation-contract roots (`GC=F`, `NQ=F`)
  aren't portable across providers (each has its own root/expiry scheme), so a
  symbol map isn't a clean fix. Left as a future item if futures reliability
  becomes a pain point.

## Whole-market scan — Grouped Daily (Movers screener)

The **Movers** tab (top gainers/losers/most-active across the *entire* US market)
is powered by Polygon/Massive's **Grouped Daily** REST endpoint, which returns
every US stock's daily bar for a date in a **single call** — on the **free**
tier. Movers needs just two calls (latest trading day + prior), well inside the
free 5/min limit, so it reuses the same `POLYGON_API_KEY`.

- OpenBB's `polygon` provider doesn't expose this market-wide route, so it lives
  in `obb_layer/grouped.py` (a thin REST client via `httpx`) — the sanctioned
  "OpenBB lacks it → extend here" path. Compute is the pure `services/movers.py`.
- **Gated:** with `POLYGON_API_KEY` unset, the Movers tab/endpoint degrades
  cleanly and `/health` reports `movers_configured:false`.
- *Note:* Massive's separate **Flat Files** (S3 bulk product, `files.massive.com`)
  give the same daily data in bulk but are **paid-tier** (free keys can list the
  bucket but not download), so we use the free Grouped Daily endpoint instead.

## News & calendar — unlock with a paid news/fundamentals key

- **FMP (recommended):** a paid **FMP** key (`FMP_API_KEY`) unlocks two things with
  no code change:
  - **B1 — economic calendar:** `obb_layer.economic_calendar` already requests
    `provider="fmp"`; the free tier 402s (degraded panel), a paid key fills it.
  - **B2 — world news:** the News feed **auto-upgrades** to a real `news.world`
    wire when a news key is present.
- **News provider auto-selection:** `services/news.py` picks the first configured
  provider in priority order — **FMP → Benzinga → Tiingo → Intrinio** — tags each
  headline with macro themes + the watchlist instruments mentioned, and **falls
  back to the free yfinance per-instrument proxy** when no key is set (or the wire
  errors). So adding any of those keys upgrades News automatically; removing them
  degrades gracefully.

## B3 — Commodity term structure (GC/CL/NG)
- **Source:** FMP `commodities-list` + `batch-commodity-quotes` (or EOD full on
  historical dates). Requires `FMP_API_KEY`; VIX stays on OpenBB CBOE.
- **Limitation:** FMP exposes listed contract months, not a dedicated CME curve
  endpoint — sufficient for contango/backwardation research context.
