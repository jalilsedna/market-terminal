"""Shared OBBject → record-dict normalization (used across obb_layer wrappers).

Kept tiny and provider-agnostic: prefer the DataFrame view, fall back to raw
`.results`, optionally sort oldest→newest by a date-like column so callers can
rely on ordering. Lives in obb_layer because it only ever handles OpenBB
response objects.
"""

from __future__ import annotations

from typing import Any


def to_records(obbject: Any, sort_by_date: bool = True) -> list[dict]:
    """Normalize an OBBject to a list of plain dicts."""
    try:
        rows = obbject.to_dataframe().reset_index().to_dict("records")
    except Exception:  # noqa: BLE001 — fall back to raw results
        results = getattr(obbject, "results", None) or []
        rows = [r.model_dump() if hasattr(r, "model_dump") else dict(r) for r in results]

    if sort_by_date:
        for key in ("date", "Date", "datetime"):
            if rows and key in rows[0]:
                rows.sort(key=lambda r: str(r.get(key)))
                break
    return rows
