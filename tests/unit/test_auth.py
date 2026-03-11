"""MCPilot — Auth Middleware + JWT tests"""
import pytest
from fastapi.testclient import TestClient
from main import app
from app.core.security import create_access_token, decode_access_token
from jose import JWTError

client = TestClient(app, raise_server_exceptions=False)

# ── Public path tests ─────────────────────────────────────────────────────────
def test_health_no_auth_required():
    assert client.get("/health").status_code == 200

def test_docs_no_auth_required():
    assert client.get("/docs").status_code == 200

# ── Protected path — no credentials ──────────────────────────────────────────
def test_gateway_no_credentials_returns_401():
    response = client.get("/gateway/servers")
    assert response.status_code == 401
    assert "detail" in response.json()

# ── API key auth ──────────────────────────────────────────────────────────────
def test_gateway_valid_api_key_passes():
    response = client.get(
        "/gateway/servers",
        headers={"X-API-Key": "mcpilot-dev-key-001"}
    )
    assert response.status_code == 200

def test_gateway_invalid_api_key_returns_401():
    response = client.get(
        "/gateway/servers",
        headers={"X-API-Key": "wrong-key"}
    )
    assert response.status_code == 401

# ── JWT auth ──────────────────────────────────────────────────────────────────
def test_gateway_valid_jwt_passes():
    token = create_access_token(
        subject="test-client",
        tenant_id="test-tenant",
        scopes=["gateway:invoke"],
    )
    response = client.get(
        "/gateway/servers",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200

def test_gateway_invalid_jwt_returns_401():
    response = client.get(
        "/gateway/servers",
        headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401

def test_gateway_malformed_bearer_returns_401():
    response = client.get(
        "/gateway/servers",
        headers={"Authorization": "NotBearer sometoken"}
    )
    assert response.status_code == 401

# ── Token issuance endpoint ───────────────────────────────────────────────────
def test_token_endpoint_valid_key():
    response = client.post(
        "/auth/token",
        headers={"X-API-Key": "mcpilot-dev-key-001"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_token_endpoint_invalid_key():
    response = client.post(
        "/auth/token",
        headers={"X-API-Key": "bad-key"}
    )
    assert response.status_code == 401

# ── JWT utility unit tests ────────────────────────────────────────────────────
def test_create_and_decode_token():
    token = create_access_token(
        subject="client-123",
        tenant_id="tenant-abc",
        scopes=["gateway:invoke", "admin"],
    )
    payload = decode_access_token(token)
    assert payload.sub == "client-123"
    assert payload.tenant_id == "tenant-abc"
    assert "gateway:invoke" in payload.scopes

def test_decode_garbage_token_raises():
    with pytest.raises(JWTError):
        decode_access_token("garbage.token.value")