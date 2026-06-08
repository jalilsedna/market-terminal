"""History router (ROADMAP C2 → C5) — daily snapshots of derived signals.

`GET /history` lists recorded series; `GET /history/{series}` returns the
time-series for one (e.g. `vol:GC`, `regime:macro`). Powers the C5 charts/alerts.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app import db
from app.schemas import Envelope

router = APIRouter(prefix="/history", tags=["History"])

_FRESHNESS = "daily snapshots of derived signals (vol/regime) — research context"


@router.get("", response_model=Envelope)
def list_series() -> Envelope:
    """The snapshot series recorded so far (e.g. vol:GC, regime:macro)."""
    return Envelope(data={"series": db.series_list()}, provider="local", freshness=_FRESHNESS)


@router.get("/{series:path}", response_model=Envelope)
def get_series(
    series: str, limit: int = Query(365, ge=1, le=2000, description="Max points (newest first)")
) -> Envelope:
    """Time-series for one snapshot series, newest first."""
    return Envelope(
        data={"series": series, "points": db.history(series, limit)},
        provider="local",
        freshness=_FRESHNESS,
    )
