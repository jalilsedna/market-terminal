"""SEC filings (ROADMAP H4 — filings subset).

"What just got filed" for a stock: recent SEC filings (8-K, 10-Q, 10-K, S-1,
4, …) with dates and links, plus a light interpretation flag for the
event-driven forms a trader cares about (8-K = material event, 4 = insider
transaction). Fault-tolerant — degrades to a clean note if the endpoint is
tier-gated. Research context, never a trade trigger.
"""

from __future__ import annotations

from typing import Any

from obb_layer import fmp
from services.signals import _num, _pick

DISCLAIMER = "Recent SEC filings (FMP) — research context, not a trade trigger."

# Forms a day-trader/event-driven reader cares about most.
_MATERIAL = {
    "8-K": "material event",
    "8-K/A": "material event (amended)",
    "4": "insider transaction",
    "10-Q": "quarterly report",
    "10-K": "annual report",
    "S-1": "registration / IPO",
    "424B": "prospectus / offering",
    "SC 13D": "activist stake",
    "SC 13G": "passive 5%+ stake",
    "13F-HR": "institutional holdings",
    "DEF 14A": "proxy statement",
}


def _flag(form: str) -> str | None:
    f = (form or "").upper().strip()
    for key, label in _MATERIAL.items():
        if f.startswith(key):
            return label
    return None


def _rows(raw: Any, limit: int) -> list[dict]:
    out: list[dict] = []
    for r in (raw if isinstance(raw, list) else [])[:limit]:
        form = str(_pick(r, "type", "formType", "form") or "")
        out.append({
            "date": str(_pick(r, "filingDate", "acceptedDate", "date") or "")[:10],
            "form": form,
            "flag": _flag(form),
            "title": _pick(r, "title", "description"),
            "url": _pick(r, "finalLink", "link", "url"),
        })
    return out


def filings(ticker: str, limit: int = 15) -> dict:
    """Recent SEC filings for one stock (fault-tolerant)."""
    ticker = (ticker or "").upper().strip()
    if not ticker:
        raise ValueError("ticker is required")

    from config import get_settings
    if not get_settings().fmp_enabled:
        return {"ticker": ticker, "enabled": False,
                "error": "Filings need an FMP key — set FMP_API_KEY.", "disclaimer": DISCLAIMER}

    errors: dict[str, str] = {}
    try:
        raw = fmp.sec_filings(ticker, limit=max(limit, 25))
    except fmp.FmpError as exc:
        errors["filings"] = str(exc)
        raw = []
    except Exception as exc:  # noqa: BLE001
        errors["filings"] = type(exc).__name__
        raw = []

    rows = _rows(raw, limit)
    material = [r for r in rows if r["flag"]]
    return {
        "ticker": ticker,
        "enabled": True,
        "count": len(rows),
        "material_count": _num(len(material)),
        "filings": rows,
        "errors": errors or None,
        "disclaimer": DISCLAIMER,
    }
