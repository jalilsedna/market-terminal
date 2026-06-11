"""Market setup (ROADMAP H7) — crypto/FX technical day-trade bias.

The equity Trade Setup (`services/signals.py`) leans on catalyst (analyst
ratings, earnings) and smart-money (insider, congressional) data that simply
does not exist for crypto/FX. This is the technical analog for those assets,
built only from data available on the FMP Starter tier per symbol:

  * Trend         — price vs 50/200-day MA (from the FMP quote).
  * Momentum      — RSI(14) + ADX (FMP technical indicators; work on crypto/FX).
  * Participation — relative volume + 52-week range position ("is it in play?").

No whole-market discovery scan (FMP's bulk crypto/FX quote feed is Ultimate-tier
only) — the screen ranks a curated majors universe (or an explicit list).

The pure scoring is reused from `services/signals.py` (trend/momentum/
participation are asset-agnostic). Research context, never a trade trigger.
"""

from __future__ import annotations

from obb_layer import fmp
from services.signals import (
    _first,
    _num,
    _pick,
    momentum_signal,
    participation,
    trend_signal,
)
from services.symbol_search import _CRYPTO_MAJORS, _FOREX_MAJORS

DISCLAIMER = (
    "Synthesized technical setup (trend + momentum + participation) — "
    "research only, not a trade trigger."
)

_SUPPORTED = ("crypto", "forex")
# Conviction ordering for ranking the screen (best long → worst).
_RANK = {"long": 2, "neutral": 1, "short": 0, "error": -1}


def _fmp_symbol(symbol: str) -> str:
    """Canonical registry symbol → FMP ticker ('BTC-USD'→'BTCUSD', 'EUR/USD'→'EURUSD')."""
    return (symbol or "").upper().replace("-", "").replace("/", "").strip()


def _conviction(score: int) -> str:
    strength = abs(score)
    return "high" if strength >= 3 else "moderate" if strength >= 2 else "low"


def _bias(score: int) -> str:
    return "long" if score >= 2 else "short" if score <= -2 else "neutral"


def market_setup(asset: str, symbol: str) -> dict:
    """Per-symbol technical setup for one crypto/FX instrument (fault-tolerant)."""
    asset = (asset or "").lower().strip()
    if asset not in _SUPPORTED:
        raise ValueError(f"market_setup supports {_SUPPORTED}, not {asset!r}")

    from config import get_settings
    if not get_settings().fmp_enabled:
        return {"symbol": (symbol or "").upper(), "asset": asset, "enabled": False,
                "error": "FMP not configured (set FMP_API_KEY)", "disclaimer": DISCLAIMER}

    fsym = _fmp_symbol(symbol)
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

    q = _first(grab("quote", lambda: fmp.quote(fsym)) or [])
    price = _num(_pick(q, "price"))
    ma50 = _num(_pick(q, "priceAvg50"))
    ma200 = _num(_pick(q, "priceAvg200"))
    vol = _num(_pick(q, "volume"))
    avg_vol = _num(_pick(q, "avgVolume"))
    yhigh = _num(_pick(q, "yearHigh"))
    ylow = _num(_pick(q, "yearLow"))

    rsi_rows = grab("rsi", lambda: fmp.technical_indicator(fsym, "rsi")) or []
    adx_rows = grab("adx", lambda: fmp.technical_indicator(fsym, "adx")) or []
    rsi = _num(_pick(_first(rsi_rows), "rsi"))
    adx = _num(_pick(_first(adx_rows), "adx"))

    t_pts, t_label = trend_signal(price, ma50, ma200)
    m_pts, m_flags, m_detail = momentum_signal(rsi, adx)
    part = participation(price, vol, avg_vol, yhigh, ylow)

    score = t_pts + m_pts
    bias = _bias(score)
    conviction = _conviction(score)
    play = "IN PLAY" if part.get("in_play") else "quiet"
    rvol = part.get("relative_volume")
    read = (f"{symbol.upper()}: {bias.upper()} ({conviction}, score {score:+d}) | {t_label} | {play}"
            + (f" — RVOL {rvol:.1f}x" if rvol is not None else ""))

    return {
        "symbol": symbol.upper(),
        "asset": asset,
        "enabled": True,
        "price": price,
        "bias": bias,
        "score": score,
        "conviction": conviction,
        "in_play": part.get("in_play", False),
        "participation": part,
        "components": {"trend": t_pts, "momentum": m_pts},
        "momentum": m_detail,
        "triggers": [t_label],
        "flags": m_flags,
        "read": read,
        "errors": errors or None,
        "disclaimer": DISCLAIMER,
    }


def _default_universe(asset: str) -> list[str]:
    return list(_CRYPTO_MAJORS[:12] if asset == "crypto" else _FOREX_MAJORS[:12])


def screen(asset: str, symbols: list[str] | None = None, limit: int = 25) -> dict:
    """Rank technical setups across a curated crypto/FX universe (or explicit list).

    No whole-market scan — FMP's bulk crypto/FX quotes are Ultimate-tier. Defaults
    to the majors (capped) to stay within Starter rate limits; results are cached.
    """
    asset = (asset or "").lower().strip()
    if asset not in _SUPPORTED:
        raise ValueError(f"market screen supports {_SUPPORTED}, not {asset!r}")

    tickers = [s.strip() for s in symbols if s and s.strip()] if symbols else _default_universe(asset)
    rows: list[dict] = []
    for sym in tickers:
        try:
            row = market_setup(asset, sym)
            if row.get("enabled") is False:
                return {"asset": asset, "enabled": False, "error": row.get("error"),
                        "disclaimer": DISCLAIMER}
            rows.append(row)
        except Exception as exc:  # noqa: BLE001 — one bad symbol must not sink the screen
            rows.append({"symbol": sym.upper(), "asset": asset, "bias": "error",
                         "score": None, "error": f"{type(exc).__name__}: {exc}"[:160]})

    rows.sort(key=lambda r: (_RANK.get(r.get("bias"), -1), r.get("score") or -99), reverse=True)
    return {
        "asset": asset,
        "enabled": True,
        "count": len(rows),
        "universe": "explicit" if symbols else "majors",
        "ranked": rows[: max(1, limit)],
        "disclaimer": DISCLAIMER,
    }
