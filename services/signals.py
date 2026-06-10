"""Trade-setup signals (ROADMAP H7) — the day-trader's daily bias engine.

FMP is EOD/catalyst data, not intraday order flow. This module turns it into the
one thing a day trader needs each morning: **is a name in play, which way, and
why** — a directional *bias* + *setup score* + concrete *triggers* that bias the
order-flow execution downstream (NinjaTrader). It is research context, never an
auto-executed signal.

It fuses five axes, each a small signed score:
  1. Trend        — price vs 50/200-day MA (structure).
  2. Momentum     — RSI (overbought/oversold) + ADX (trend strength).
  3. Catalyst     — analyst rating change, price-target trend, earnings proximity,
                    fresh news.
  4. Smart money  — insider buy/sell ratio + congressional (senate/house) buys.
  5. Context      — the existing bottom-up + macro conviction (`services/brain`).
Plus a non-directional **participation** read: relative volume (today vs avg) and
ADX — "is it actually tradeable today?".

Pure scoring functions (no network) are unit-tested; `trade_setup()` wires data.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from obb_layer import fmp

DISCLAIMER = (
    "Synthesized trade-setup context (FMP catalysts + positioning + technicals) — "
    "research only, not investment advice or an auto-executed trade signal."
)

# Relative-volume threshold above which a name is "in play" for the day.
_IN_PLAY_RVOL = 1.5
# ADX above this = a real trend (momentum tradeable); below ~20 = chop.
_TREND_ADX = 25.0


def _num(x: Any) -> float | None:
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def _first(x: Any) -> dict:
    if isinstance(x, list):
        return x[0] if x else {}
    return x if isinstance(x, dict) else {}


def _pick(d: dict, *keys: str) -> Any:
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return None


# --- Pure scoring axes ------------------------------------------------------ #
def trend_signal(price: float | None, ma50: float | None, ma200: float | None) -> tuple[int, str]:
    """Price vs 50/200-day MA → (-2..+2, label)."""
    if price is None or ma50 is None or ma200 is None:
        return 0, "trend unknown"
    above50, above200 = price > ma50, price > ma200
    if above50 and above200:
        return 2, "uptrend (price > 50 & 200 MA)"
    if not above50 and not above200:
        return -2, "downtrend (price < 50 & 200 MA)"
    # Mixed: lean by the faster MA, which a day trader weights more.
    return (1, "recovering (price > 50 MA, < 200 MA)") if above50 else \
           (-1, "rolling over (price < 50 MA, > 200 MA)")


def momentum_signal(rsi: float | None, adx: float | None) -> tuple[int, list[str], dict]:
    """RSI + ADX → (signed points, flags, detail). RSI biases direction modestly;
    extremes flag exhaustion; ADX gauges trend strength (participation)."""
    points = 0
    flags: list[str] = []
    if rsi is not None:
        if rsi >= 70:
            flags.append(f"RSI {rsi:.0f} — overbought (long-exhaustion risk)")
        elif rsi <= 30:
            flags.append(f"RSI {rsi:.0f} — oversold (short-exhaustion risk)")
        points += 1 if rsi > 55 else -1 if rsi < 45 else 0
    trending = bool(adx is not None and adx >= _TREND_ADX)
    if adx is not None and adx < 20:
        flags.append(f"ADX {adx:.0f} — choppy / no trend")
    return points, flags, {"rsi": rsi, "adx": adx, "trending": trending}


def _grades_net(row: dict) -> int:
    """Weighted analyst-consensus net from a grades row (strong = 2x)."""
    sb = _num(_pick(row, "analystRatingsStrongBuy", "strongBuy")) or 0
    b = _num(_pick(row, "analystRatingsBuy", "buy")) or 0
    s = _num(_pick(row, "analystRatingsSell", "sell")) or 0
    ss = _num(_pick(row, "analystRatingsStrongSell", "strongSell")) or 0
    return int(sb * 2 + b - s - ss * 2)


def catalyst_signal(grades_hist: Any, pt_summary: dict, news: Any,
                    earnings: Any) -> tuple[int, list[str], dict]:
    """Rating change + PT trend + fresh news + earnings proximity → (points, triggers, detail)."""
    points = 0
    triggers: list[str] = []
    detail: dict = {}

    rows = grades_hist if isinstance(grades_hist, list) else []
    if len(rows) >= 2:
        now_net, prior_net = _grades_net(rows[0]), _grades_net(rows[1])
        detail["grades_net"] = now_net
        if now_net > prior_net:
            points += 1
            triggers.append("analyst consensus improving (recent upgrade)")
        elif now_net < prior_net:
            points -= 1
            triggers.append("analyst consensus deteriorating (recent downgrade)")

    pm = _num(_pick(pt_summary, "lastMonthAvgPriceTarget"))
    pq = _num(_pick(pt_summary, "lastQuarterAvgPriceTarget"))
    if pm is not None and pq is not None and pq > 0:
        detail["pt_month"] = pm
        if pm > pq * 1.01:
            points += 1
            triggers.append("price targets rising (month > quarter)")
        elif pm < pq * 0.99:
            points -= 1
            triggers.append("price targets falling (month < quarter)")

    fresh = 0
    cutoff = datetime.now(UTC).date() - timedelta(days=3)
    for item in (news if isinstance(news, list) else []):
        d = _pick(item, "publishedDate", "date")
        try:
            if date.fromisoformat(str(d)[:10]) >= cutoff:
                fresh += 1
        except (TypeError, ValueError):
            continue
    if fresh:
        detail["fresh_news"] = fresh
        triggers.append(f"{fresh} fresh headline(s) in last 3d — volatility catalyst")

    ev = _earnings_proximity(earnings)
    detail["earnings"] = ev
    if ev.get("days_away") is not None and 0 <= ev["days_away"] <= 7:
        triggers.append(f"earnings in {ev['days_away']}d — event risk")
    return points, triggers, detail


def _earnings_proximity(earnings: Any) -> dict:
    rows = earnings if isinstance(earnings, list) else []
    today = datetime.now(UTC).date()
    upcoming, last = None, None
    parsed = []
    for r in rows:
        d = _pick(r, "date")
        try:
            parsed.append((date.fromisoformat(str(d)[:10]), r))
        except (TypeError, ValueError):
            continue
    parsed.sort(key=lambda x: x[0])
    upcoming = next((x for x in parsed if x[0] >= today), None)
    last = next((x for x in reversed(parsed) if x[0] < today), None)
    out: dict = {"days_away": (upcoming[0] - today).days if upcoming else None,
                 "next_date": upcoming[0].isoformat() if upcoming else None}
    if last:
        a = _num(_pick(last[1], "epsActual"))
        e = _num(_pick(last[1], "epsEstimated"))
        if a is not None and e is not None:
            out["last_surprise"] = "beat" if a > e else "miss" if a < e else "in-line"
    return out


def smart_money_signal(insider_stats: Any, insider_search: Any,
                       senate: Any, house: Any) -> tuple[int, list[str], dict]:
    """Insider buy/sell ratio + recent insider purchases + congress buys → (points, triggers, detail)."""
    points = 0
    triggers: list[str] = []
    detail: dict = {}

    stat = _first(insider_stats)
    acq = _num(_pick(stat, "acquiredTransactions", "totalAcquired"))
    dis = _num(_pick(stat, "disposedTransactions", "totalDisposed"))
    if acq is not None and dis is not None and (acq + dis) > 0:
        ratio = acq / (acq + dis)
        detail["insider_buy_ratio"] = round(ratio, 2)
        if ratio >= 0.6:
            points += 1
            triggers.append(f"insiders net buying ({ratio:.0%} of txns acquisitions)")
        elif ratio <= 0.3:
            points -= 1
            triggers.append(f"insiders net selling ({ratio:.0%} acquisitions)")

    recent_buys = _count_recent_purchases(insider_search, days=90,
                                          type_keys=("transactionType",),
                                          buy_markers=("P-", "purchase", "buy", "a-"))
    if recent_buys:
        detail["insider_recent_buys_90d"] = recent_buys

    congress_net = _congress_net(senate) + _congress_net(house)
    if congress_net:
        detail["congress_net_90d"] = congress_net
        if congress_net > 0:
            points += 1
            triggers.append(f"net congressional buying (+{congress_net} recent)")
        elif congress_net < 0:
            triggers.append(f"net congressional selling ({congress_net} recent)")
    return points, triggers, detail


def _count_recent_purchases(rows: Any, *, days: int, type_keys: tuple[str, ...],
                            buy_markers: tuple[str, ...]) -> int:
    cutoff = datetime.now(UTC).date() - timedelta(days=days)
    n = 0
    for r in (rows if isinstance(rows, list) else []):
        d = _pick(r, "transactionDate", "filingDate", "date")
        try:
            if date.fromisoformat(str(d)[:10]) < cutoff:
                continue
        except (TypeError, ValueError):
            continue
        t = ""
        for k in type_keys:
            t = str(_pick(r, k) or "").lower()
            if t:
                break
        if any(m in t for m in buy_markers):
            n += 1
    return n


def _congress_net(rows: Any, days: int = 120) -> int:
    """+1 per recent purchase, -1 per sale (net direction of political flow)."""
    cutoff = datetime.now(UTC).date() - timedelta(days=days)
    net = 0
    for r in (rows if isinstance(rows, list) else []):
        d = _pick(r, "transactionDate", "disclosureDate", "date")
        try:
            if date.fromisoformat(str(d)[:10]) < cutoff:
                continue
        except (TypeError, ValueError):
            continue
        t = str(_pick(r, "type", "transactionType") or "").lower()
        if "purchase" in t or "buy" in t:
            net += 1
        elif "sale" in t or "sell" in t:
            net -= 1
    return net


def participation(price: float | None, volume: float | None, avg_volume: float | None,
                  year_high: float | None, year_low: float | None) -> dict:
    """Non-directional 'is it in play': relative volume + 52w range position."""
    rvol = (volume / avg_volume) if (volume and avg_volume) else None
    pos = None
    if price is not None and year_high is not None and year_low is not None and year_high > year_low:
        pos = round((price - year_low) / (year_high - year_low), 2)
    return {
        "relative_volume": round(rvol, 2) if rvol is not None else None,
        "in_play": bool(rvol is not None and rvol >= _IN_PLAY_RVOL),
        "range_position_52w": pos,  # 0 = at 52w low, 1 = at 52w high
    }


def fuse(trend: tuple, momentum: tuple, catalyst: tuple, smart: tuple,
         context_lean: int) -> dict:
    """Combine the signed axes into bias + score + conviction."""
    t_pts, t_label = trend
    m_pts, m_flags, _ = momentum
    c_pts, c_trigs, _ = catalyst
    s_pts, s_trigs, _ = smart
    score = t_pts + m_pts + c_pts + s_pts + context_lean
    bias = "long" if score >= 2 else "short" if score <= -2 else "neutral"
    strength = abs(score)
    conviction = "high" if strength >= 4 else "moderate" if strength >= 2 else "low"
    triggers = [t_label] + c_trigs + s_trigs
    return {"bias": bias, "score": score, "conviction": conviction,
            "components": {"trend": t_pts, "momentum": m_pts, "catalyst": c_pts,
                           "smart_money": s_pts, "context": context_lean},
            "triggers": triggers, "flags": m_flags}


# --- Composition ------------------------------------------------------------ #
def _context_lean(symbol: str) -> tuple[int, str | None]:
    """Reuse the bottom-up + macro brain as a low-weight directional context."""
    try:
        from services import brain
        v = brain.verdict(symbol)
        conv = v.get("conviction")
        lean = 1 if conv == "constructive" else -1 if conv == "cautious" else 0
        return lean, v.get("summary")
    except Exception:  # noqa: BLE001 — context is optional
        return 0, None


def trade_setup(symbol: str) -> dict:
    """Per-symbol daily trade-setup bias for one ticker (fault-tolerant)."""
    symbol = symbol.upper().strip()
    from config import get_settings
    if not get_settings().fmp_enabled:
        return {"symbol": symbol, "enabled": False,
                "error": "FMP not configured (set FMP_API_KEY)", "disclaimer": DISCLAIMER}

    errors: dict[str, str] = {}

    def grab(name: str, fn, default=None):
        try:
            return fn()
        except fmp.FmpDisabled:
            errors[name] = "FMP not configured"
        except fmp.FmpError as exc:
            errors[name] = str(exc)
        except Exception as exc:  # noqa: BLE001
            errors[name] = type(exc).__name__
        return default

    q = _first(grab("quote", lambda: fmp.quote(symbol)) or [])
    price = _num(_pick(q, "price"))
    ma50 = _num(_pick(q, "priceAvg50"))
    ma200 = _num(_pick(q, "priceAvg200"))
    vol = _num(_pick(q, "volume"))
    avg_vol = _num(_pick(q, "avgVolume"))
    yhigh = _num(_pick(q, "yearHigh"))
    ylow = _num(_pick(q, "yearLow"))

    rsi_rows = grab("rsi", lambda: fmp.technical_indicator(symbol, "rsi")) or []
    adx_rows = grab("adx", lambda: fmp.technical_indicator(symbol, "adx")) or []
    rsi = _num(_pick(_first(rsi_rows), "rsi"))
    adx = _num(_pick(_first(adx_rows), "adx"))

    grades_hist = grab("grades", lambda: fmp.grades_historical(symbol, limit=6)) or []
    pt_sum = _first(grab("price_target", lambda: fmp.price_target_summary(symbol)) or [])
    news = grab("news", lambda: fmp.stock_news(symbol, limit=10)) or []
    earn = grab("earnings", lambda: fmp.earnings(symbol)) or []

    ins_stat = grab("insider_stats", lambda: fmp.insider_statistics(symbol)) or []
    ins_search = grab("insider_search", lambda: fmp.insider_search(symbol, limit=30)) or []
    senate = grab("senate", lambda: fmp.senate_trades(symbol)) or []
    house = grab("house", lambda: fmp.house_trades(symbol)) or []

    trend = trend_signal(price, ma50, ma200)
    momentum = momentum_signal(rsi, adx)
    catalyst = catalyst_signal(grades_hist, pt_sum, news, earn)
    smart = smart_money_signal(ins_stat, ins_search, senate, house)
    context_lean, context_summary = _context_lean(symbol)

    fused = fuse(trend, momentum, catalyst, smart, context_lean)
    part = participation(price, vol, avg_vol, yhigh, ylow)

    read = _read(symbol, fused, part, catalyst[2])
    return {
        "symbol": symbol,
        "enabled": True,
        "price": price,
        "bias": fused["bias"],
        "score": fused["score"],
        "conviction": fused["conviction"],
        "in_play": part["in_play"],
        "participation": part,
        "components": fused["components"],
        "triggers": fused["triggers"],
        "flags": fused["flags"],
        "momentum": momentum[2],
        "catalyst_detail": catalyst[2],
        "smart_money_detail": smart[2],
        "context": context_summary,
        "read": read,
        "errors": errors or None,
        "disclaimer": DISCLAIMER,
    }


# --- Daily hit-list: market-wide morning scanner --------------------------- #
def hitlist_candidates(movers_data: dict) -> list[dict]:
    """Flatten movers (gainers/losers/most-active) into unique candidates with a
    day-direction tag. Pure."""
    cands: dict[str, dict] = {}
    for r in movers_data.get("gainers", []) or []:
        cands.setdefault(r["ticker"], {**r, "day_dir": "up"})
    for r in movers_data.get("losers", []) or []:
        cands.setdefault(r["ticker"], {**r, "day_dir": "down"})
    for r in movers_data.get("most_active", []) or []:
        d = "up" if (_num(r.get("change_1d_pct")) or 0) >= 0 else "down"
        cands.setdefault(r["ticker"], {**r, "day_dir": d})
    return list(cands.values())


def score_candidate(move_pct: float | None, catalyst_pts: int, smart_pts: int) -> dict:
    """The day's move sets the in-play direction (weighted 2x); catalyst + smart
    money confirm or diverge. Returns bias + score + confluence. Pure."""
    move_pts = 0
    if move_pct is not None:
        move_pts = 2 if move_pct > 0 else -2 if move_pct < 0 else 0
    extra = catalyst_pts + smart_pts
    score = move_pts + extra
    bias = "long" if score >= 2 else "short" if score <= -2 else "neutral"
    confluence = bool((move_pts > 0 and extra > 0) or (move_pts < 0 and extra < 0))
    return {"score": score, "bias": bias, "confluence": confluence}


def rank_hitlist(rows: list[dict]) -> list[dict]:
    """Confluence first, then conviction (|score|), then raw intensity (|move|). Pure."""
    return sorted(
        rows,
        key=lambda r: (
            1 if r.get("confluence") else 0,
            abs(r.get("score") or 0),
            abs(_num(r.get("change_1d_pct")) or 0),
        ),
        reverse=True,
    )


def _enrich_candidate(ticker: str) -> tuple[int, int, list[str], dict]:
    """Light per-ticker enrichment for the hit-list: catalyst (grades + earnings)
    and smart money (insider stats). Few calls each (cached); fault-tolerant."""
    def safe(fn, default):
        try:
            return fn()
        except Exception:  # noqa: BLE001
            return default

    grades = safe(lambda: fmp.grades_historical(ticker, limit=6), []) or []
    earn = safe(lambda: fmp.earnings(ticker), []) or []
    stats = safe(lambda: fmp.insider_statistics(ticker), []) or []
    c_pts, c_trigs, c_det = catalyst_signal(grades, {}, [], earn)
    s_pts, s_trigs, _ = smart_money_signal(stats, [], [], [])
    return c_pts, s_pts, c_trigs + s_trigs, c_det.get("earnings", {})


def daily_hitlist(limit: int = 15, scan_depth: int = 20, min_move_pct: float = 2.0,
                  min_price: float = 5.0, min_dollar_volume: float = 25_000_000.0) -> dict:
    """Market-wide morning scanner: today's movers, enriched with catalyst +
    smart-money signals, ranked into the most tradeable names with a directional
    lean. Needs FMP (signals) + POLYGON_API_KEY (whole-market movers feed).

    The liquidity floor (`min_price`/`min_dollar_volume`) is deliberately tighter
    than the raw movers feed's $1 / $5M defaults: a micro-cap can spike 30% and
    clear $5M of dollar-volume on one day, so the loose floor surfaces untradeable
    penny names. Day-trading wants real depth, hence ~$5 / ~$25M here.
    Research context, never a trade trigger."""
    from config import get_settings
    if not get_settings().fmp_enabled:
        return {"enabled": False, "error": "FMP not configured (set FMP_API_KEY)",
                "disclaimer": DISCLAIMER}

    from services import movers as movers_svc
    try:
        m = movers_svc.movers(top_n=25, min_price=min_price, min_dollar_volume=min_dollar_volume)
    except Exception as exc:  # noqa: BLE001 — movers needs POLYGON_API_KEY
        return {"enabled": True, "hitlist": [], "count": 0,
                "error": f"movers feed unavailable ({type(exc).__name__}) — set POLYGON_API_KEY",
                "disclaimer": DISCLAIMER}

    cands = [c for c in hitlist_candidates(m)
             if abs(_num(c.get("change_1d_pct")) or 0) >= min_move_pct]
    cands.sort(key=lambda c: abs(_num(c.get("change_1d_pct")) or 0), reverse=True)

    rows: list[dict] = []
    for c in cands[: max(1, scan_depth)]:
        ticker = c["ticker"]
        move = _num(c.get("change_1d_pct"))
        c_pts, s_pts, trigs, ev = _enrich_candidate(ticker)
        sc = score_candidate(move, c_pts, s_pts)
        event_risk = ev.get("days_away") is not None and 0 <= ev["days_away"] <= 7
        if event_risk:
            trigs = trigs + [f"earnings in {ev['days_away']}d — event risk"]
        rows.append({
            "ticker": ticker,
            "day_dir": c.get("day_dir"),
            "price": c.get("close"),
            "change_1d_pct": move,
            "dollar_volume": c.get("dollar_volume"),
            "bias": sc["bias"],
            "score": sc["score"],
            "confluence": sc["confluence"],
            "event_risk": event_risk,
            "triggers": trigs,
            "read": f"{ticker}: {sc['bias'].upper()} ({move:+.1f}% today"
                    + (", confluence" if sc["confluence"] else "") + ")"
                    + (" — " + "; ".join(trigs[:3]) if trigs else ""),
        })

    ranked = rank_hitlist(rows)[: max(1, limit)]
    return {
        "enabled": True,
        "as_of": m.get("as_of"),
        "scanned": len(rows),
        "count": len(ranked),
        "long_count": sum(1 for r in ranked if r["bias"] == "long"),
        "short_count": sum(1 for r in ranked if r["bias"] == "short"),
        "liquidity_floor": {"min_price": min_price, "min_dollar_volume": min_dollar_volume},
        "hitlist": ranked,
        "method": "Whole-market movers (EOD) enriched with analyst rating changes, "
                  "earnings proximity, and insider flow; ranked by confluence + "
                  "conviction + intensity.",
        "disclaimer": DISCLAIMER,
    }


def _read(symbol: str, fused: dict, part: dict, catalyst_detail: dict) -> str:
    rvol = part.get("relative_volume")
    play = "IN PLAY" if part.get("in_play") else "quiet"
    bits = [f"{symbol}: {fused['bias'].upper()} bias ({fused['conviction']} conviction, score {fused['score']:+d})"]
    bits.append(f"{play}" + (f" — RVOL {rvol:.1f}x" if rvol is not None else ""))
    if fused["triggers"]:
        bits.append("; ".join(fused["triggers"][:4]))
    ev = (catalyst_detail or {}).get("earnings", {})
    if ev.get("days_away") is not None and 0 <= ev["days_away"] <= 7:
        bits.append(f"earnings in {ev['days_away']}d")
    return " | ".join(bits)
