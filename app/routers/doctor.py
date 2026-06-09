"""Doctor router (ROADMAP A6) — operational self-diagnostic.

`GET /doctor` returns provider config, the EOD chain, SQLite/volume state, cache
stats, and advisory checks (see `services/doctor.py`). Behind the normal auth
gate (not in OPEN_PATHS), so it never leaks operational detail to anonymous
callers; /health stays the public liveness probe.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.auth import current_user, users
from app.schemas import Envelope
from services import doctor

router = APIRouter(prefix="/doctor", tags=["meta"])


@router.get("", response_model=Envelope)
def doctor_report(request: Request) -> Envelope:
    """Deep operational report + advisory checks (auth-gated)."""
    user = current_user(request)
    data = doctor.report(user=user, role=users.role(user))
    return Envelope(data=data, provider="local", freshness="live diagnostic")
