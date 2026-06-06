"""FastAPI application entry point.

This is the terminal's own API surface. Per SPEC.md §2/§6, our FastAPI is only
justified where it adds value over OpenBB's auto-generated REST/MCP — merged
multi-source views, our caching/normalization, and watchlist logic. It is not a
1:1 re-export of OpenBB's router layer.

Run locally:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Warm OpenBB on the main thread at startup.

    OpenBB rebuilds its static package whenever the installed extension set
    changes, and that rebuild installs a SIGTERM handler via signal.signal(),
    which only works on the main thread. If the first OpenBB import happened
    lazily inside a request (FastAPI runs sync endpoints in a worker thread), it
    raises "signal only works in main thread of the main interpreter" on every
    call. Triggering it here, during startup on the main thread, performs any
    one-time rebuild safely; request-time calls then reuse the built package.
    """
    import logging

    # Quiet transient-failure noise from provider HTTP layers. Our services
    # already catch these and degrade the affected panel, but OpenBB's FRED
    # client dumps large asyncio tracebacks ("Future exception was never
    # retrieved") and yfinance prints "possibly delisted" on any network blip /
    # rate limit. Silence theirs; our own logs are untouched.
    for _noisy in ("asyncio", "yfinance"):
        logging.getLogger(_noisy).setLevel(logging.CRITICAL)

    from app.precache import start as start_precache
    from obb_layer.client import get_obb

    get_obb()
    stop_precache = start_precache(settings.precache_interval_min)
    try:
        yield
    finally:
        stop_precache()


app = FastAPI(
    title=settings.app_name,
    description=(
        "Private multi-asset research terminal built on OpenBB (library). "
        "Research and analytics only — no execution. See SPEC.md."
    ),
    version="0.0.1",
    lifespan=lifespan,
)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness check + which providers have keys configured."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "providers_configured": settings.configured_providers(),
        "precache_interval_min": settings.precache_interval_min,
        "alice_url": settings.alice_url,
    }


# Routers (one per view) are registered here as they ship — see SPEC.md §4/§5.
# Phase 1 (complete): V1 Macro Dashboard, V4 COT/Positioning, V2 Watchlist.
# Phase 2 (complete): V3 News Feed, V5 Term Structure, V6 Screener/Sector Rotation.
from app.routers import cot, macro, news, screener, term_structure, watchlist

app.include_router(macro.router)
app.include_router(cot.router)
app.include_router(watchlist.router)
app.include_router(news.router)
app.include_router(term_structure.router)
app.include_router(screener.router)


# Serve the single-page dashboard (web/) at the root. Mounted LAST so all API
# routes above take precedence; the static mount only catches '/', '/app.js',
# '/styles.css', etc. (Phase 3 — SPEC.md §5 step 11.)
from pathlib import Path

from fastapi.staticfiles import StaticFiles

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
