"""MCPilot — Health endpoint unit tests"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_200():
    assert client.get("/health").status_code == 200

def test_health_shape():
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert data["service"] == "mcpilot"
    assert "uptime_seconds" in data
    assert "environment" in data

def test_readiness_200():
    assert client.get("/health/ready").status_code == 200

def test_readiness_checks():
    data = client.get("/health/ready").json()
    assert data["checks"]["api"] == "ok"

def test_root_200():
    assert client.get("/").status_code == 200

def test_gateway_tool_stub_501():
    response = client.post(
        "/gateway/tool",
        json={
            "server_id": "test",
            "tool_name": "echo",
            "parameters": {"text": "hello"},
        },
        headers={"X-API-Key": "mcpilot-dev-key-001"}
    )
    assert response.status_code == 501

def test_gateway_servers_empty():
    response = client.get(
        "/gateway/servers",
        headers={"X-API-Key": "mcpilot-dev-key-001"}
    )
    assert response.json()["servers"] == []