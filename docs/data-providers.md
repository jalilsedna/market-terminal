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

### Get a free, sturdier provider
- **Tiingo** — free tier, far steadier than yfinance for equities/ETFs. Sign up
  at <https://www.tiingo.com>, then set `TIINGO_API_KEY=...` and
  `EOD_PROVIDERS=tiingo,yfinance`. (`obb_layer/client.py` already pushes the key
  into OpenBB's credential store.)
- **Polygon / FMP** — alternatives; add the key and put the provider first in the
  chain.

### Not yet in the chain (why)
- **Crypto / FX / futures** stay on yfinance — providers use **different symbol
  formats** (yfinance `BTC-USD` / `EURUSD` / `GC=F` vs Tiingo `btcusd` / …), so a
  naive fallback would send the wrong symbol. A per-provider **symbol-mapping
  layer** is the follow-up that unlocks the chain for these (B-next).

## Still open (B1–B3)
- **B1 — Economic calendar:** paywalled on FMP free; V1's calendar is degraded.
- **B2 — World news:** FMP free paywalled; worked around with per-instrument
  yfinance news.
- **B3 — Commodity term-structure curves (GC/CL/NG):** yfinance 401s; only VIX
  works. Needs a futures-curve source.
