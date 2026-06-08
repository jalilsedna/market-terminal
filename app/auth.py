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
import os
import time
from urllib.parse import quote

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from app import db
from config import get_settings

SESSION_COOKIE = "mt_session"
SESSION_TTL = 7 * 24 * 60 * 60  # one week

# Paths reachable without authentication: liveness, the login/registration flows,
# and the favicon (browsers request it pre-login).
OPEN_PATHS = {"/health", "/login", "/logout", "/register", "/favicon.ico"}

_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    """Salted PBKDF2-SHA256 hash → "iterations$salt_hex$hash_hex" (stdlib only)."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{_PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_hash(password: str, stored: str) -> bool:
    """Constant-time check of a password against a stored PBKDF2 hash."""
    try:
        iterations, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
    except Exception:  # noqa: BLE001 — a malformed hash is just "no match"
        return False
    return hmac.compare_digest(dk.hex(), hash_hex)


# --------------------------------------------------------------------------- #
# Identity — DB-backed user store (ROADMAP F2) with an env-admin bootstrap.     #
# --------------------------------------------------------------------------- #
class Users:
    """Account store: a SQLite `users` table, plus the env admin
    (ADMIN_USERNAME/ADMIN_PASSWORD) as an always-available bootstrap login."""

    def _is_env_admin(self, username: str, password: str) -> bool:
        s = get_settings()
        if not s.admin_password:
            return False
        return hmac.compare_digest(username or "", s.admin_username) and hmac.compare_digest(
            password or "", s.admin_password
        )

    def verify_password(self, username: str, password: str) -> bool:
        """True if the credentials match an enabled DB user or the env admin."""
        u = db.user_get(username)
        if u and not u["disabled"] and verify_hash(password, u["pw_hash"]):
            return True
        return self._is_env_admin(username, password)

    def role(self, username: str | None) -> str | None:
        """'admin' / 'user' for a known, enabled account; else None."""
        if not username:
            return None
        u = db.user_get(username)
        if u:
            return None if u["disabled"] else u["role"]
        s = get_settings()
        if s.admin_password and hmac.compare_digest(username, s.admin_username):
            return "admin"
        return None

    def exists(self, username: str) -> bool:
        if db.user_get(username) is not None:
            return True
        s = get_settings()
        return bool(s.admin_password and username == s.admin_username)

    def create(self, username: str, password: str, role: str = "user") -> bool:
        """Create a user; False if the username is taken."""
        if self.exists(username):
            return False
        return db.user_create(username, hash_password(password), role)

    def list(self) -> list[dict]:
        return db.user_list()

    def set_disabled(self, username: str, disabled: bool) -> bool:
        return db.user_set_disabled(username, disabled)


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
def current_user(request: Request) -> str | None:
    """Who's making this request: the username from a valid session cookie, the
    sentinel 'token' for a Bearer client, or None (anonymous / auth disabled)."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and verify_token(auth[7:]):
        return "token"
    cookie = request.cookies.get(SESSION_COOKIE)
    return verify_session(cookie) if cookie else None


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
