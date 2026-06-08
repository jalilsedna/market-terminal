"""Auth module + middleware — the gate that protects the public deploy.

Mirrors the manual smoke tests run while building A8, as automated regression
checks. No OpenBB, no network: a throwaway FastAPI app carries the real
`auth_middleware`.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# --------------------------------------------------------------------------- #
# Unit: signing, tokens, passwords, expiry.                                    #
# --------------------------------------------------------------------------- #
def test_session_roundtrip(auth_env):
    from app import auth

    cookie = auth.issue_session("jalil")
    assert auth.verify_session(cookie) == "jalil"


def test_tampered_session_rejected(auth_env):
    from app import auth

    cookie = auth.issue_session("jalil")
    assert auth.verify_session(cookie + "x") is None
    assert auth.verify_session("garbage") is None


def test_expired_session_rejected(auth_env):
    from app import auth

    body = auth._b64(b"jalil:1")  # exp far in the past (epoch 1)
    expired = f"{body}.{auth._sign(body)}"
    assert auth.verify_session(expired) is None


def test_token_check(auth_env):
    from app import auth

    assert auth.verify_token("tok-123") is True
    assert auth.verify_token("nope") is False
    assert auth.verify_token("") is False


def test_password_check(auth_env):
    from app import auth

    assert auth.users.verify_password("jalil", "pw-456") is True
    assert auth.users.verify_password("jalil", "wrong") is False
    assert auth.users.verify_password("intruder", "pw-456") is False


# --------------------------------------------------------------------------- #
# Middleware: the request-gating behaviour.                                    #
# --------------------------------------------------------------------------- #
@pytest.fixture
def client(auth_env):
    from app.auth import auth_middleware

    app = FastAPI()
    app.middleware("http")(auth_middleware)

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/macro/dashboard")
    def macro():
        return {"data": 1}

    return TestClient(app)


def test_health_is_open(client):
    assert client.get("/health").status_code == 200


def test_api_rejects_anonymous(client):
    r = client.get("/macro/dashboard")
    assert r.status_code == 401
    assert r.json()["error"] == "unauthorized"


def test_bearer_token_grants_access(client):
    r = client.get("/macro/dashboard", headers={"Authorization": "Bearer tok-123"})
    assert r.status_code == 200


def test_browser_redirected_to_login(client):
    r = client.get(
        "/macro/dashboard",
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "/login" in r.headers["location"]


def test_session_cookie_grants_access(client):
    from app import auth

    client.cookies.set(auth.SESSION_COOKIE, auth.issue_session("jalil"))
    assert client.get("/macro/dashboard").status_code == 200


def test_query_token_sets_cookie(client):
    r = client.get("/macro/dashboard?token=tok-123")
    assert r.status_code == 200
    assert "mt_session" in r.headers.get("set-cookie", "") or client.cookies.get("mt_session")


class _FakeReq:
    """Minimal stand-in for a Starlette Request (current_user only reads
    .headers.get and .cookies.get)."""

    def __init__(self, headers=None, cookies=None):
        self.headers = headers or {}
        self.cookies = cookies or {}


def test_current_user(auth_env):
    """current_user resolves Bearer → 'token', valid cookie → username, else None."""
    from app import auth

    assert auth.current_user(_FakeReq(headers={"authorization": "Bearer tok-123"})) == "token"
    assert auth.current_user(_FakeReq(headers={"authorization": "Bearer nope"})) is None
    assert auth.current_user(
        _FakeReq(cookies={auth.SESSION_COOKIE: auth.issue_session("jalil")})
    ) == "jalil"
    assert auth.current_user(_FakeReq()) is None


def test_disabled_auth_is_noop(no_auth_env):
    """With no credentials, the middleware lets everything through."""
    from app.auth import auth_middleware

    app = FastAPI()
    app.middleware("http")(auth_middleware)

    @app.get("/macro/dashboard")
    def macro():
        return {"data": 1}

    client = TestClient(app)
    assert client.get("/macro/dashboard").status_code == 200
