"""Shared response schemas.

Every endpoint returns the same normalized envelope (SPEC.md §5, item 3) so the
frontend and any AI client see one consistent shape, including an explicit
data-freshness label (SPEC.md §6 — never imply tradeable intraday signals).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """Standard response envelope for all terminal endpoints."""

    ok: bool = True
    data: T | None = None
    provider: str | None = Field(
        default=None, description="OpenBB provider that served the data."
    )
    freshness: str | None = Field(
        default=None,
        description="Data freshness label, e.g. 'EOD', 'delayed', 'weekly (COT)'.",
    )
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None
