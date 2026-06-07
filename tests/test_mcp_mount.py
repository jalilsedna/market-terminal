"""The FastMCP-into-FastAPI mount + auth — the A8 integration that lets one
service serve the web UI, REST API, and agent feed under a single auth gate.

Rebuilds the exact mounting pattern from app/main.py against a throwaway FastMCP
(so no OpenBB is needed) and verifies a real MCP `initialize` handshake passes
through the Bearer gate.
"""

from __future__ import annotations

import contextlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings


@pytest.fixture
def mcp_client(auth_env):
    from app.auth import auth_middleware

    mcp = FastMCP("test-terminal")

    @mcp.tool()
    def ping() -> str:
        "health probe"
        return "pong"

    # Same three knobs app/main.py sets for a clean mount.
    mcp.settings.stateless_http = True
    mcp.settings.streamable_http_path = "/"
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    )
    mcp_app = mcp.streamable_http_app()

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        async with mcp.session_manager.run():
            yield

    app = FastAPI(lifespan=lifespan)
    app.middleware("http")(auth_middleware)
    app.mount("/mcp", mcp_app)
    return TestClient(app)


_INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "ci", "version": "1"},
    },
}
_HEADERS = {
    "Authorization": "Bearer tok-123",
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def test_mcp_rejects_anonymous(mcp_client):
    with mcp_client as c:
        r = c.post("/mcp/", json=_INIT)
        assert r.status_code == 401


def test_mcp_initialize_with_bearer(mcp_client):
    with mcp_client as c:
        r = c.post("/mcp/", json=_INIT, headers=_HEADERS)
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        assert '"result"' in r.text
        assert "protocolVersion" in r.text
