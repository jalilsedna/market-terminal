# Data providers & reliability (ROADMAP B)

The terminal uses **FMP as the primary market-data provider** (equities, ETFs,
crypto, FX, commodities, futures proxies, news, calendar, fundamentals). FRED
and CFTC remain free for macro/COT. **Yahoo Finance is not used anywhere.**

## Required key

Set **`FMP_API_KEY`** (Railway → Variables). Without it, price panels, news,
fundamentals, and commodity curves degrade; macro (FRED) and COT still work.

## B4 — EOD provider fallback (shipped)

Equity/ETF/crypto/FX fetchers try a configurable **provider chain** until one
returns data:

```
EOD_PROVIDERS=fmp,tiingo,polygon
```

- Default chain is **FMP-first** (`fmp,tiingo,polygon`). Tiingo/Polygon add
  resilience when their keys are set.
- `/health` reports the active `eod_providers` chain.
- **Verify it's really serving** (a fallback chain fails *silently*): run
  `python -m scripts.probe_providers`.

### Optional resilience keys
- **Tiingo** — `TIINGO_API_KEY` at <https://www.tiingo.com>
- **Polygon / Massive** — `POLYGON_API_KEY` (Massive.com rebrand; same key)
- **FMP** — primary; should be first in the chain

### Futures prices
CME continuation symbols (`GC=F`, `NQ=F`, …) use **direct FMP REST**
(`obb_layer/fmp_market.py`) — mapped to FMP tickers (`GCUSD`, `^NDX`, …).

### Crypto / FX symbol mapping
Per-provider formats live in `obb_layer/symbol_map.py` (e.g. `BTC-USD` → FMP
`BTCUSD`, Polygon `X:BTCUSD`). Unit-tested in `tests/test_symbol_map.py`.

## Whole-market scan — Grouped Daily (Movers screener)

The **Movers** tab uses Polygon/Massive **Grouped Daily** (`obb_layer/grouped.py`).
Requires `POLYGON_API_KEY`; degrades cleanly when unset.

## News & calendar

- **Economic calendar (B1):** FMP via OpenBB (`provider="fmp"`).
- **World news (B2):** auto-selects FMP → Benzinga → Tiingo → Intrinio when keys
  are set (`services/news.py`).
- **Company/symbol news:** FMP `news/stock` REST when no world wire is available.

## B3 — Commodity term structure (GC/CL/NG)

FMP `commodities-list` + `batch-commodity-quotes` (or EOD full on historical
dates). VIX stays on OpenBB CBOE.
