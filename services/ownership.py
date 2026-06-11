"""Smart Money / Ownership (ROADMAP H3 — equity subset).

The "who's actually buying/selling" lens for a stock: corporate **insider**
transactions (buy/sell ratio + recent filings) and **congressional** trades
(Senate + House), fused into an interpreted lean. This data already feeds
`trade_setup` internally; here it gets its own interpreted view + Alice tool +
`decision_brief` section.

Confirmed on the FMP Starter tier (insider statistics/search, senate-trades,
house-trades). ETF holdings, 13F institutional, and ESG remain Ultimate-gated
(out of scope for this subset). Fault-tolerant; research context, never advice.
"""

from __future__ import annotations

from typing import Any

from obb_layer import fmp
from services.signals import _first, _num, _pick, smart_money_signal

DISCLAIMER = (
    "Insider + congressional trading read (FMP) — disclosed transactions, "
    "research context, not advice or a trade trigger."
)

_BUY_MARKERS = ("p-", "purchase", "buy", "a-", "acquired")
_SELL_MARKERS = ("s-", "sale", "sell", "d-", "disposed")


def _txn_side(raw: str) -> str:
    t = (raw or "").lower()
    if any(m in t for m in _BUY_MARKERS):
        return "buy"
    if any(m in t for m in _SELL_MARKERS):
        return "sell"
    return "—"


def _insider_rows(rows: Any, limit: int = 8) -> list[dict]:
    out: list[dict] = []
    for r in (rows if isinstance(rows, list) else [])[:limit]:
        shares = _num(_pick(r, "securitiesTransacted", "shares"))
        price = _num(_pick(r, "price"))
        out.append({
            "date": str(_pick(r, "transactionDate", "filingDate", "date") or "")[:10],
            "name": _pick(r, "reportingName", "name", "typeOfOwner"),
            "role": _pick(r, "typeOfOwner", "officerTitle"),
            "side": _txn_side(str(_pick(r, "transactionType", "acquisitionOrDisposition") or "")),
            "shares": shares,
            "value": round(shares * price, 0) if (shares is not None and price is not None) else None,
        })
    return out


def _congress_rows(rows: Any, chamber: str, limit: int = 6) -> list[dict]:
    out: list[dict] = []
    for r in (rows if isinstance(rows, list) else [])[:limit]:
        name = (_pick(r, "representative", "office", "senator")
                or " ".join(str(x) for x in (_pick(r, "firstName"), _pick(r, "lastName")) if x).strip()
                or None)
        out.append({
            "date": str(_pick(r, "transactionDate", "disclosureDate", "date") or "")[:10],
            "name": name,
            "chamber": chamber,
            "side": _txn_side(str(_pick(r, "type", "transactionType") or "")),
            "amount": _pick(r, "amount", "range"),
        })
    return out


def _lean(score: int) -> str:
    return "buying" if score >= 1 else "selling" if score <= -1 else "neutral"


def ownership(ticker: str) -> dict:
    """Interpreted insider + congressional read for one stock (fault-tolerant)."""
    ticker = (ticker or "").upper().strip()
    if not ticker:
        raise ValueError("ticker is required")

    from config import get_settings
    if not get_settings().fmp_enabled:
        return {"ticker": ticker, "enabled": False,
                "error": "Ownership needs an FMP key — set FMP_API_KEY.", "disclaimer": DISCLAIMER}

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

    stats = grab("insider_statistics", lambda: fmp.insider_statistics(ticker)) or []
    search = grab("insider_search", lambda: fmp.insider_search(ticker, limit=30)) or []
    senate = grab("senate", lambda: fmp.senate_trades(ticker)) or []
    house = grab("house", lambda: fmp.house_trades(ticker)) or []

    points, triggers, detail = smart_money_signal(stats, search, senate, house)
    stat = _first(stats)

    return {
        "ticker": ticker,
        "enabled": True,
        "smart_money": {
            "score": points,
            "lean": _lean(points),
            "insider_buy_ratio": detail.get("insider_buy_ratio"),
            "insider_recent_buys_90d": detail.get("insider_recent_buys_90d"),
            "congress_net_90d": detail.get("congress_net_90d"),
            "acquired_txns": _num(_pick(stat, "acquiredTransactions", "totalAcquired")),
            "disposed_txns": _num(_pick(stat, "disposedTransactions", "totalDisposed")),
            "triggers": triggers,
        },
        "insider_recent": _insider_rows(search),
        "congress_recent": _congress_rows(senate, "Senate") + _congress_rows(house, "House"),
        "errors": errors or None,
        "disclaimer": DISCLAIMER,
    }
