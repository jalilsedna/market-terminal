"""Alerts router (ROADMAP C5) — rules over recorded history.

`GET /alerts` returns every rule with its current triggered state (evaluated
against the latest daily snapshot). `POST /alerts` creates a rule; `DELETE
/alerts/{id}` removes one; `POST /alerts/{id}/enabled` toggles it. Flags are
research context — the terminal never acts on them.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.schemas import Envelope
from services import alerts as alerts_svc

router = APIRouter(prefix="/alerts", tags=["Alerts"])

_FRESHNESS = "evaluated against the latest daily snapshot — research context"


class AddAlert(BaseModel):
    series: str            # e.g. 'vol:GC', 'regime:macro'
    metric: str            # regime | percentile | vol | score
    op: str                # ==/!= (regime) or >/>=/</<= (numeric)
    threshold: Any         # regime level (str) or number
    label: str | None = None


@router.get("", response_model=Envelope)
def list_alerts() -> Envelope:
    """All alert rules with current triggered state + a triggered count."""
    return Envelope(data=alerts_svc.evaluate(), provider="local", freshness=_FRESHNESS)


@router.post("", response_model=Envelope)
def create_alert(req: AddAlert) -> Envelope:
    """Create a rule watching one metric of one recorded series."""
    try:
        rule = alerts_svc.add_rule(
            series=req.series, metric=req.metric, op=req.op,
            threshold=req.threshold, label=req.label,
        )
    except alerts_svc.RuleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Envelope(data=rule, provider="local")


@router.delete("/{alert_id}", response_model=Envelope)
def delete_alert(alert_id: str) -> Envelope:
    if not alerts_svc.remove_rule(alert_id):
        raise HTTPException(status_code=404, detail="no such alert")
    return Envelope(data={"removed": alert_id}, provider="local")


@router.post("/{alert_id}/enabled", response_model=Envelope)
def toggle_alert(
    alert_id: str, enabled: bool = Query(..., description="enable (1) or disable (0)")
) -> Envelope:
    if not alerts_svc.set_enabled(alert_id, enabled):
        raise HTTPException(status_code=404, detail="no such alert")
    return Envelope(data={"id": alert_id, "enabled": enabled}, provider="local")
