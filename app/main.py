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
from mcp.server.transport_security import TransportSecuritySettings

from config import get_settings

settings = get_settings()

# --- Research MCP feed, mounted into this same service (Phase A8) -------------
# The terminal exposes its research as MCP tools. Rather than run a second
# process/port, we mount the FastMCP app into this FastAPI service at `/mcp`, so
# one Railway deploy serves the web UI, the REST API, AND the agent feed under a
# single domain and a single auth gate (see app/auth.py).
#
# Three settings make mounting clean:
#   * stateless_http      — each request is self-contained; no long-lived session
#     to babysit, which is ideal behind a mount and for a read-only feed.
#   * streamable_http_path "/" — the sub-app serves at its own root; we add the
#     "/mcp" prefix via app.mount() below (avoids a doubled "/mcp/mcp").
#   * transport_security  — FastMCP's DNS-rebinding guard rejects unknown Host
#     headers (e.g. *.railway.app); we disable it because our own Bearer/session
#     auth already protects the endpoint.
from mcp_server import mcp as research_mcp

research_mcp.settings.stateless_http = True
research_mcp.settings.streamable_http_path = "/"
research_mcp.settings.transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False
)
_mcp_app = research_mcp.streamable_http_app()  # also creates session_manager


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
    # Run the mounted MCP feed's session manager for the app's lifetime. FastMCP
    # requires this to be entered exactly once within a lifespan when its ASGI
    # app is mounted into a host application.
    async with research_mcp.session_manager.run():
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


# Access control. Registered before the routes so it wraps every request,
# including the mounted MCP feed and the static SPA. No-op when auth is disabled
# (keyless local dev); enforced as soon as a token/admin password is set.
from app.auth import auth_middleware

app.middleware("http")(auth_middleware)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness check + which providers have keys configured. Always reachable
    (Railway's healthcheck hits this) — never behind auth."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "auth_enabled": settings.auth_enabled,
        "providers_configured": settings.configured_providers(),
        "eod_providers": settings.eod_provider_chain,
        "movers_configured": settings.movers_enabled,
        "precache_interval_min": settings.precache_interval_min,
        "alice_url": settings.alice_url,
    }


# Routers (one per view) are registered here as they ship — see SPEC.md §4/§5.
# Phase 1 (complete): V1 Macro Dashboard, V4 COT/Positioning, V2 Watchlist.
# Phase 2 (complete): V3 News Feed, V5 Term Structure, V6 Screener/Sector Rotation.
from app.routers import (
    alerts,
    analysis,
    brain,
    chart,
    cot,
    custom,
    doctor,
    fundamentals,
    history,
    instruments,
    macro,
    news,
    screener,
    term_structure,
    tradingview,
    volatility,
    watchlist,
)

app.include_router(macro.router)
app.include_router(cot.router)
app.include_router(instruments.router)
app.include_router(watchlist.router)
app.include_router(news.router)
app.include_router(term_structure.router)
app.include_router(screener.router)
app.include_router(analysis.router)
app.include_router(volatility.router)
app.include_router(custom.router)
app.include_router(history.router)
app.include_router(alerts.router)
app.include_router(chart.router)
app.include_router(doctor.router)
app.include_router(tradingview.router)
app.include_router(fundamentals.router)
app.include_router(brain.router)


from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.auth import SESSION_COOKIE, current_user, set_session_cookie, users

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@app.get("/whoami", include_in_schema=False)
def whoami(request: Request) -> dict:
    """Who's signed in + their role (for the web UI's session bar / Admin tab).
    Behind auth when enabled; nulls when auth is off (keyless local dev)."""
    user = current_user(request)
    return {
        "auth_enabled": settings.auth_enabled,
        "user": user,
        "role": users.role(user),
        "registration_open": settings.registration_open,
    }


def _require_admin(request: Request) -> None:
    """Raise 403 unless the caller is an admin (F2 admin endpoints)."""
    if users.role(current_user(request)) != "admin":
        raise HTTPException(status_code=403, detail="admin only")


@app.get("/register", include_in_schema=False)
def register_page() -> HTMLResponse:
    """Self-service sign-up page (open only when registration_open)."""
    closed = "" if settings.registration_open else (
        '<p class="err">Registration is currently closed — ask an admin for an account.</p>'
    )
    html = (_WEB_DIR / "register.html").read_text(encoding="utf-8").replace("<!--CLOSED-->", closed)
    return HTMLResponse(html)


@app.post("/register", include_in_schema=False)
async def register_submit(request: Request):
    """Create a 'user' account and sign them in (when registration is open)."""
    if not settings.registration_open:
        raise HTTPException(status_code=403, detail="registration is closed")
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    if len(username) < 3 or len(password) < 8:
        raise HTTPException(status_code=400, detail="username ≥3 chars, password ≥8 chars")
    if not users.create(username, password, role="user"):
        raise HTTPException(status_code=409, detail="username already taken")
    resp = RedirectResponse("/", status_code=303)
    set_session_cookie(resp, username, secure=request.url.scheme == "https")
    return resp


@app.get("/admin/users", include_in_schema=False)
def admin_list_users(request: Request) -> dict:
    """List accounts (admin only)."""
    _require_admin(request)
    return {"users": users.list(), "registration_open": settings.registration_open}


class _NewUser(BaseModel):
    username: str
    password: str
    role: str = "user"


@app.post("/admin/users", include_in_schema=False)
def admin_create_user(request: Request, body: _NewUser) -> dict:
    """Create an account (admin only)."""
    _require_admin(request)
    if body.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="role must be 'user' or 'admin'")
    if len(body.username.strip()) < 3 or len(body.password) < 8:
        raise HTTPException(status_code=400, detail="username ≥3 chars, password ≥8 chars")
    if not users.create(body.username.strip(), body.password, role=body.role):
        raise HTTPException(status_code=409, detail="username already taken")
    return {"ok": True, "users": users.list()}


@app.post("/admin/users/{username}/disabled", include_in_schema=False)
def admin_set_disabled(request: Request, username: str, disabled: bool = True) -> dict:
    """Enable/disable an account (admin only)."""
    _require_admin(request)
    users.set_disabled(username, disabled)
    return {"ok": True, "users": users.list()}


def _login_html(next_url: str = "/", error: str = "") -> str:
    """Render the login page with the post-login redirect target and any error."""
    html = (_WEB_DIR / "login.html").read_text(encoding="utf-8")
    safe_next = next_url if next_url.startswith("/") else "/"
    html = html.replace("__NEXT__", safe_next)
    if error:
        html = html.replace("<!--ERROR-->", f'<p class="err">{error}</p>')
    return html


@app.get("/login", include_in_schema=False)
def login_page(next: str = "/") -> HTMLResponse:
    """Serve the browser login form (open — see auth.OPEN_PATHS)."""
    return HTMLResponse(_login_html(next))


@app.post("/login", include_in_schema=False)
async def login_submit(request: Request):
    """Validate credentials, set the session cookie, and redirect on success."""
    form = await request.form()
    username = str(form.get("username", ""))
    password = str(form.get("password", ""))
    next_url = str(form.get("next", "/")) or "/"
    if users.verify_password(username, password):
        target = next_url if next_url.startswith("/") else "/"
        resp = RedirectResponse(target, status_code=303)
        set_session_cookie(resp, username, secure=request.url.scheme == "https")
        return resp
    return HTMLResponse(
        _login_html(next_url, error="Invalid username or password."), status_code=401
    )


@app.api_route("/logout", methods=["GET", "POST"], include_in_schema=False)
def logout() -> RedirectResponse:
    """Clear the session cookie and return to the login page."""
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


# Mount the research MCP feed at /mcp (configured above). Registered before the
# catch-all static mount so it takes precedence.
app.mount("/mcp", _mcp_app, name="mcp")

# Serve the single-page dashboard (web/) at the root. Mounted LAST so all API
# routes above take precedence; the static mount only catches '/', '/app.js',
# '/styles.css', etc. (Phase 3 — SPEC.md §5 step 11.)
app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
