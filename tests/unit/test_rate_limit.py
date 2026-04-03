"""
MCPilot — Rate limiting + error handler tests
"""
import sys
import pytest
from fastapi.testclient import TestClient
from main import app
from app.mcp.manager import MCPManager
from app.mcp.registry import MCPServerRegistry
from app.core.metrics import MetricsStore

windows_anyio_bug = pytest.mark.xfail(
    sys.platform == "win32",
    reason="Windows anyio cancel scope bug with SelectorEventLoop — passes in isolation and on Linux CI",
    strict=False,
)


@pytest.fixture(scope="module")
def rl_client():
    """Dedicated client for rate limit tests — avoids cancel scope conflicts."""
    app.state.mcp_manager = MCPManager(MCPServerRegistry())
    app.state.metrics     = MetricsStore()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

@windows_anyio_bug
def test_validation_error_returns_422(rl_client):
    response = rl_client.post(
        "/gateway/tool",
        json={"parameters": "not-a-dict"},
        headers={"X-API-Key": "mcpilot-dev-key-001"},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "validation_error"
    assert "errors" in data

@windows_anyio_bug
def test_404_returns_consistent_envelope(rl_client):
    response = rl_client.get(
        "/nonexistent-path",
        headers={"X-API-Key": "mcpilot-dev-key-001"}
    )
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "path" in data

@windows_anyio_bug
def test_health_not_rate_limited(rl_client):
    for _ in range(10):
        assert rl_client.get("/health").status_code == 200

@windows_anyio_bug
def test_gateway_returns_404_unknown_server(rl_client):
    response = rl_client.post(
        "/gateway/tool",
        json={
            "server_id": "ghost-server",
            "tool_name": "echo",
            "parameters": {},
        },
        headers={"X-API-Key": "mcpilot-dev-key-001"},
    )
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "not_found"

@windows_anyio_bug
def test_response_time_header_present(rl_client):
    response = rl_client.get("/health")
    assert "x-response-time-ms" in response.headers