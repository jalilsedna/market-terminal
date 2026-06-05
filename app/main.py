"""FastAPI application entry point.

This is the terminal's own API surface. Per SPEC.md §2/§6, our FastAPI is only
justified where it adds value over OpenBB's auto-generated REST/MCP — merged
multi-source views, our caching/normalization, and watchlist logic. It is not a
1:1 re-export of OpenBB's router layer.

Run locally:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI

from config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Private multi-asset research terminal built on OpenBB (library). "
        "Research and analytics only — no execution. See SPEC.md."
    ),
    version="0.0.1",
)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness check + which providers have keys configured."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "providers_configured": settings.configured_providers(),
    }


# Routers (one per view) are registered here as they ship — see SPEC.md §4/§5.
# Phase 1: V1 Macro Dashboard, V4 COT/Positioning, V2 Watchlist.
#
# from app.routers import macro, cot, watchlist
# app.include_router(macro.router)
# app.include_router(cot.router)
# app.include_router(watchlist.router)
