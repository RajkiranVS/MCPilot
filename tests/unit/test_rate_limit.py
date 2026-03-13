"""
MCPilot — Rate limiting + error handler tests
"""
import pytest
from fastapi.testclient import TestClient


def test_validation_error_returns_422(client):
    """Missing required fields should return structured 422."""
    response = client.post(
        "/gateway/tool",
        json={"server_id": "test"},   # missing tool_name and parameters
        headers={"X-API-Key": "mcpilot-dev-key-001"},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "validation_error"
    assert "errors" in data


def test_404_returns_consistent_envelope(client):
    """Unknown routes behind auth return 401 before 404 — correct behaviour.
    Test 404 envelope via a known protected path with bad server."""
    response = client.get(
        "/nonexistent-path",
        headers={"X-API-Key": "mcpilot-dev-key-001"}
    )
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "path" in data


def test_health_not_rate_limited(client):
    """Health endpoint should never be rate limited."""
    for _ in range(10):
        assert client.get("/health").status_code == 200


def test_gateway_returns_404_unknown_server(client):
    """Unknown server_id returns 404 not 500."""
    response = client.post(
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


def test_response_time_header_present(client):
    """RequestLoggingMiddleware should inject X-Response-Time-Ms."""
    response = client.get("/health")
    assert "x-response-time-ms" in response.headers