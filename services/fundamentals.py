"""Fundamentals view (ROADMAP H, Phase 1) — the terminal's bottom-up brain.

Composes a per-ticker fundamentals dashboard from FMP: company profile, valuation,
quality/health, growth, statement highlights, peers, and revenue segmentation.

Built fault-tolerant like the macro dashboard — each block fetches independently,
so an FMP tier-gated or failed endpoint degrades to an `errors` entry instead of
breaking the view. Field extraction is **defensive** (`_pick` tries several FMP
field-name variants) because FMP's keys differ a little across plans/versions; the
raw values are kept so we can lock names once we see live responses. The
interpreted "fundamental read" verdict comes in Phase 2.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from obb_layer import fmp


def _first(x: Any) -> dict:
    """FMP endpoints return a list; take the most recent (first) record."""
    if isinstance(x, list):
        return x[0] if x else {}
    return x if isinstance(x, dict) else {}


def _pick(d: dict, *keys: str) -> Any:
    """First present, non-None value among `keys` (FMP name variants)."""
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return None


def _profile(p: dict) -> dict:
    return {
        "name": _pick(p, "companyName", "name"),
        "sector": _pick(p, "sector"),
        "industry": _pick(p, "industry"),
        "exchange": _pick(p, "exchangeShortName", "exchange"),
        "price": _pick(p, "price"),
        "market_cap": _pick(p, "marketCap", "mktCap"),
        "beta": _pick(p, "beta"),
        "currency": _pick(p, "currency"),
        "ceo": _pick(p, "ceo"),
        "employees": _pick(p, "fullTimeEmployees"),
        "country": _pick(p, "country"),
        "website": _pick(p, "website"),
        "description": _pick(p, "description"),
    }


def _valuation(ratios: dict, metrics: dict) -> dict:
    return {
        # stable API uses priceToEarningsRatio; keep v3 names as fallbacks.
        "pe": _pick(ratios, "priceToEarningsRatio", "priceEarningsRatio", "peRatio") or _pick(metrics, "peRatio", "priceToEarningsRatioTTM"),
        "ps": _pick(ratios, "priceToSalesRatio", "priceSalesRatio") or _pick(metrics, "priceToSalesRatio"),
        "pb": _pick(ratios, "priceToBookRatio", "pbRatio") or _pick(metrics, "pbRatio"),
        "ev_ebitda": _pick(ratios, "enterpriseValueMultiple", "evToEbitda") or _pick(metrics, "evToEBITDA", "enterpriseValueOverEBITDA"),
        "dividend_yield": _pick(ratios, "dividendYield") or _pick(metrics, "dividendYield"),
        "fcf_yield": _pick(metrics, "freeCashFlowYield"),
        "earnings_yield": _pick(metrics, "earningsYield"),
    }


def _quality(ratios: dict, metrics: dict, scores: dict) -> dict:
    return {
        "piotroski": _pick(scores, "piotroskiScore"),
        "altman_z": _pick(scores, "altmanZScore"),
        "roe": _pick(ratios, "returnOnEquity") or _pick(metrics, "roe", "returnOnEquity"),
        "roic": _pick(metrics, "roic", "returnOnInvestedCapital"),
        "net_margin": _pick(ratios, "netProfitMargin"),
        "gross_margin": _pick(ratios, "grossProfitMargin"),
        "operating_margin": _pick(ratios, "operatingProfitMargin"),
        "current_ratio": _pick(ratios, "currentRatio") or _pick(metrics, "currentRatio"),
        # stable API uses debtToEquityRatio; keep v3 names as fallbacks.
        "debt_to_equity": _pick(ratios, "debtToEquityRatio", "debtEquityRatio", "debtToEquity") or _pick(metrics, "debtToEquityRatio", "debtToEquity"),
    }


def _growth(g: dict) -> dict:
    return {
        "revenue": _pick(g, "growthRevenue", "revenueGrowth"),
        "eps": _pick(g, "growthEPS", "epsgrowth", "growthEPSDiluted"),
        "net_income": _pick(g, "growthNetIncome"),
        "fiscal_year": _pick(g, "date", "calendarYear"),
    }


def _segments(rows: Any) -> dict | None:
    """Latest revenue segmentation record ({segment: value}), if available."""
    rec = _first(rows)
    # FMP returns {date:..., <segment>: value, ...} or nested under a key.
    seg = {k: v for k, v in rec.items() if k not in ("date", "symbol", "period") and isinstance(v, (int, float))}
    return seg or None


def _median(values: list) -> float | None:
    vals = sorted(v for v in values if isinstance(v, (int, float)))
    if not vals:
        return None
    n, m = len(vals), len(vals) // 2
    return vals[m] if n % 2 else (vals[m - 1] + vals[m]) / 2


def _pe_series(ratios_series: Any) -> list:
    """Positive P/E values across the ratios history (for the 5y median)."""
    out = []
    for r in ratios_series if isinstance(ratios_series, list) else []:
        pe = _pick(r, "priceToEarningsRatio", "priceEarningsRatio", "peRatio")
        if isinstance(pe, (int, float)) and pe > 0:
            out.append(pe)
    return out


def _ratio(numer: Any, denom: Any) -> float | None:
    try:
        return (float(numer) - float(denom)) / float(denom) if denom else None
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _dcf(rec: dict, price: Any) -> dict:
    """DCF fair value + gap vs current price (gap>0 => undervalued)."""
    fair = _pick(rec, "dcf", "equityValuePerShare", "discountedCashFlow")
    return {"fair_value": fair, "gap": _ratio(fair, price)}


def _analyst(pt: dict, ratings: dict, price: Any) -> dict:
    """Consensus price target (+ implied upside) and rating snapshot."""
    target = _pick(pt, "targetConsensus", "priceTargetConsensus", "targetMedian", "targetHigh")
    rating = _pick(ratings, "rating", "ratingRecommendation") or _pick(pt, "consensus")
    return {"target": target, "upside": _ratio(target, price), "rating": rating}


def _next_earnings(rows: Any) -> dict:
    """Next upcoming earnings date + days away, and the latest reported surprise."""
    rows = rows if isinstance(rows, list) else []
    today = datetime.now(UTC).date()
    upcoming = []
    for r in rows:
        d = _pick(r, "date", "epsDate")
        try:
            dd = date.fromisoformat(str(d)[:10])
        except (TypeError, ValueError):
            continue
        upcoming.append((dd, r))
    upcoming.sort(key=lambda x: x[0])
    nxt = next((x for x in upcoming if x[0] >= today), None)
    last = next((x for x in reversed(upcoming) if x[0] < today), None)
    return {
        "next_date": nxt[0].isoformat() if nxt else None,
        "days_away": (nxt[0] - today).days if nxt else None,
        "last_eps_actual": _pick(last[1], "epsActual", "eps") if last else None,
        "last_eps_estimate": _pick(last[1], "epsEstimated", "epsEstimate") if last else None,
    }


def _read(valuation: dict, quality: dict, growth: dict, dcf: dict, analyst: dict, earnings: dict) -> dict:
    """Interpreted one-line fundamental verdict — research context, not advice."""
    parts: list[str] = []
    flags: list[str] = []

    # Valuation: PRIMARY axis is relative (current P/E vs its own 5y median) — a
    # naive DCF over-flags premium compounders as "expensive", so DCF is kept as
    # informational context, not the label. Fall back to DCF only if no P/E history.
    pe, pe_med = valuation.get("pe"), valuation.get("pe_median")
    gap = dcf.get("gap")
    valuation_label = None
    rel = (pe / pe_med) if (isinstance(pe, (int, float)) and isinstance(pe_med, (int, float)) and pe_med > 0 and pe > 0) else None
    if rel is not None:
        valuation_label = "cheap" if rel < 0.85 else "expensive" if rel > 1.15 else "fair"
        detail = f"P/E {pe:.0f} vs 5y-med {pe_med:.0f}"
        if isinstance(gap, (int, float)):
            detail += f", DCF {gap:+.0%}"
        parts.append(f"{valuation_label} ({detail})")
    elif isinstance(gap, (int, float)):
        valuation_label = "cheap" if gap > 0.15 else "expensive" if gap < -0.15 else "fair"
        parts.append(f"{valuation_label} (DCF {gap:+.0%})")

    pio, z = quality.get("piotroski"), quality.get("altman_z")
    quality_label = None
    if pio is not None:
        quality_label = "strong" if pio >= 7 else "weak" if pio <= 3 else "mixed"
        detail = f"Piotroski {int(pio)}" + (f", Z {z:.1f}" if isinstance(z, (int, float)) else "")
        parts.append(f"{quality_label} quality ({detail})")
        if isinstance(z, (int, float)) and z < 1.8:
            flags.append(f"Altman-Z {z:.1f} — distress zone")

    rg = growth.get("revenue")
    growth_label = None
    if rg is not None:
        growth_label = "growing" if rg > 0.02 else "declining" if rg < -0.02 else "flat"
        parts.append(f"{growth_label} (rev {rg:+.0%})")

    up = analyst.get("upside")
    if up is not None:
        parts.append(f"analysts {up:+.0%}")

    days = earnings.get("days_away")
    if days is not None:
        parts.append(f"earnings in {days}d")
        if 0 <= days <= 14:
            flags.append(f"earnings in {days}d — event risk")

    return {
        "verdict": " · ".join(parts) or "insufficient fundamental data",
        "labels": {"valuation": valuation_label, "quality": quality_label, "growth": growth_label},
        "flags": flags,
    }


def dashboard(symbol: str) -> dict:
    """Per-ticker fundamentals dashboard. Fault-tolerant: failed/gated FMP blocks
    land in `errors` rather than raising."""
    symbol = symbol.upper().strip()
    errors: dict[str, str] = {}

    def grab(name: str, fn):
        try:
            return fn()
        except fmp.FmpDisabled:
            errors[name] = "FMP not configured"
        except fmp.FmpError as exc:
            errors[name] = str(exc)
        except Exception as exc:  # noqa: BLE001 — never let one block break the view
            errors[name] = f"{type(exc).__name__}"
        return None

    profile = _first(grab("profile", lambda: fmp.profile(symbol)) or [])
    ratios_series = grab("ratios", lambda: fmp.ratios(symbol, limit=5)) or []  # 5y for the P/E median
    ratios = _first(ratios_series)
    metrics = _first(grab("key_metrics", lambda: fmp.key_metrics(symbol, limit=1)) or [])
    scores = _first(grab("scores", lambda: fmp.financial_scores(symbol)) or [])
    growth = _first(grab("growth", lambda: fmp.income_growth(symbol, limit=1)) or [])
    peers_raw = grab("peers", lambda: fmp.peers(symbol)) or []
    geo = grab("revenue_geo", lambda: fmp.revenue_geo(symbol))
    product = grab("revenue_product", lambda: fmp.revenue_product(symbol))

    # H2 — valuation / analyst / calendars
    dcf_rec = _first(grab("dcf", lambda: fmp.dcf(symbol)) or [])
    pt_rec = _first(grab("price_target", lambda: fmp.price_target_consensus(symbol)) or [])
    ratings_rec = _first(grab("ratings", lambda: fmp.ratings_snapshot(symbol)) or [])
    earn_rows = grab("earnings", lambda: fmp.earnings(symbol)) or []
    div_rec = _first(grab("dividends", lambda: fmp.dividends(symbol, limit=1)) or [])

    price = _pick(profile, "price")
    valuation = _valuation(ratios, metrics)
    valuation["pe_median"] = _median(_pe_series(ratios_series))  # 5y median for relative valuation
    quality = _quality(ratios, metrics, scores)
    growth_block = _growth(growth)
    dcf = _dcf(dcf_rec, price)
    analyst = _analyst(pt_rec, ratings_rec, price)
    earnings_block = _next_earnings(earn_rows)

    peers = _first(peers_raw).get("peersList") if peers_raw else None
    if peers is None and isinstance(peers_raw, list):
        peers = [p.get("symbol") for p in peers_raw if isinstance(p, dict) and p.get("symbol")]

    return {
        "symbol": symbol,
        "enabled": True,
        "read": _read(valuation, quality, growth_block, dcf, analyst, earnings_block),
        "profile": _profile(profile),
        "valuation": valuation,
        "quality": quality,
        "growth": growth_block,
        "dcf": dcf,
        "analyst": analyst,
        "earnings": earnings_block,
        "dividend": {"yield": _pick(div_rec, "yield", "dividendYield"), "amount": _pick(div_rec, "dividend", "adjDividend")},
        "peers": peers or [],
        "segmentation": {"geographic": _segments(geo), "product": _segments(product)},
        "errors": errors or None,
        "disclaimer": "Fundamental research context (FMP) — not investment advice or a trade trigger.",
    }
