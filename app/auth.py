"""Access control for the public deploy (Phase A8).

The terminal is single-user research today, but once it's reachable on the
internet the web UI, REST API, and mounted MCP feed all have to be gated. This
module is that gate, with two credential paths that share **one** identity
layer:

* **Browser** → a `/login` page sets a signed **session cookie**.
* **Programmatic clients** (Alice / MCP / API) → an `Authorization: Bearer
  <token>` header.

Both resolve through `Users`, which today is a single admin from the
environment. It is deliberately shaped so a **database-backed user store +
self-service registration** drops in later by replacing `Users` alone — the
middleware, cookie signing, and routes never need to change.

When neither a token nor an admin password is configured (`auth_enabled` is
false), the middleware is a no-op, so keyless local dev is unchanged.

Cookie signing is dependency-free (HMAC-SHA256), so this adds no new packages.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from urllib.parse import quote

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from config import get_settings

SESSION_COOKIE = "mt_session"
SESSION_TTL = 7 * 24 * 60 * 60  # one week

# Paths reachable without authentication: liveness, the login flow itself, and
# the favicon (browsers request it pre-login).
OPEN_PATHS = {"/health", "/login", "/logout", "/favicon.ico"}


# --------------------------------------------------------------------------- #
# Identity — the one place that knows "who may access". Swap this class for a   #
# DB-backed store to add multi-user + registration; nothing else changes.      #
# --------------------------------------------------------------------------- #
class Users:
    """Account store. Current implementation: a single admin from env."""

    def verify_password(self, username: str, password: str) -> bool:
        """True if (username, password) match the configured admin."""
        s = get_settings()
        if not s.admin_password:
            return False
        # constant-time on both fields to avoid leaking either via timing
        ok_user = hmac.compare_digest(username or "", s.admin_username)
        ok_pass = hmac.compare_digest(password or "", s.admin_password)
        return ok_user and ok_pass


users = Users()


def verify_token(token: str) -> bool:
    """True if `token` matches the configured Bearer token (constant-time)."""
    s = get_settings()
    if not s.auth_token:
        return False
    return hmac.compare_digest(token or "", s.auth_token)


# --------------------------------------------------------------------------- #
# Signed session cookie (HMAC-SHA256, no external dependency).                  #
# --------------------------------------------------------------------------- #
def _secret() -> bytes:
    """Key for cookie signatures. Prefers an explicit SESSION_SECRET so logins
    survive redeploys; falls back to the Bearer token. Both are hashed so the
    raw secret never becomes the literal HMAC key."""
    s = get_settings()
    raw = s.session_secret or s.auth_token or ""
    return hashlib.sha256(raw.encode()).digest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _sign(body: str) -> str:
    return _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())


def issue_session(username: str) -> str:
    """Mint a signed `body.signature` session value for `username`."""
    exp = int(time.time()) + SESSION_TTL
    body = _b64(f"{username}:{exp}".encode())
    return f"{body}.{_sign(body)}"


def verify_session(cookie: str) -> str | None:
    """Return the username if the cookie is well-formed, unexpired, and the
    signature checks out; otherwise None."""
    try:
        body, sig = cookie.rsplit(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _sign(body)):
        return None
    try:
        pad = "=" * (-len(body) % 4)
        username, exp = base64.urlsafe_b64decode(body + pad).decode().rsplit(":", 1)
    except Exception:  # noqa: BLE001 — any decode failure is just "invalid"
        return None
    if int(exp) < int(time.time()):
        return None
    return username


def set_session_cookie(resp: Response, username: str, *, secure: bool) -> None:
    """Attach a fresh session cookie for `username` to `resp`."""
    resp.set_cookie(
        SESSION_COOKIE,
        issue_session(username),
        max_age=SESSION_TTL,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def _wants_html(request: Request) -> bool:
    """A browser navigation (GET expecting HTML) — redirect it to /login rather
    than returning a JSON 401."""
    return request.method == "GET" and "text/html" in request.headers.get("accept", "")


# --------------------------------------------------------------------------- #
# The middleware.                                                              #
# --------------------------------------------------------------------------- #
async def auth_middleware(request: Request, call_next):
    """Gate every request unless it carries a valid Bearer token (programmatic)
    or session cookie (browser). No-op when auth is disabled."""
    settings = get_settings()
    if not settings.auth_enabled:
        return await call_next(request)

    path = request.url.path
    if path in OPEN_PATHS:
        return await call_next(request)

    # 1) Bearer token — Alice / MCP / API clients.
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and verify_token(auth[7:]):
        return await call_next(request)

    secure = request.url.scheme == "https"

    # 2) ?token=<bearer> convenience for a browser the first time: unlock and
    #    drop a session cookie so subsequent requests don't need the query.
    qtoken = request.query_params.get("token")
    if qtoken and verify_token(qtoken):
        resp = await call_next(request)
        set_session_cookie(resp, "token", secure=secure)
        return resp

    # 3) Session cookie — a logged-in browser.
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie and verify_session(cookie):
        return await call_next(request)

    # Unauthenticated: send browsers to the login page, everyone else a 401.
    if _wants_html(request):
        return RedirectResponse(f"/login?next={quote(path)}", status_code=303)
    return JSONResponse(
        {"error": "unauthorized", "detail": "Provide a valid session cookie or Bearer token."},
        status_code=401,
    )
