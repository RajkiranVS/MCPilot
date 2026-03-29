"""
MCPilot — SAT-003: Redaction Pipeline Integration Tests
Proves PHI is detected and redacted end-to-end through the full gateway stack.

Pipeline under test:
  Client sends PHI → AuthMiddleware → Gateway → scan_input() → MCP Server
                                                             ↓
  Client receives redacted ← scan_output() ← MCP response ←─┘

Uses the echo server — ideal for redaction testing because:
  echo(text="John Smith SSN 123-45-6789") → returns exactly what was sent
  This means we can verify BOTH input redaction (what reaches the server)
  AND output redaction (what comes back to the client) in a single call.
"""
import asyncio
import sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from httpx import AsyncClient, ASGITransport
from main import app
from app.mcp.manager import MCPManager
from app.mcp.registry import MCPServerRegistry, MCPServerConfig, TransportType

API_KEY = "mcpilot-dev-key-001"
HEADERS = {"X-API-Key": API_KEY}

_loop   = None
_manager = None


def setup_module(module):
    global _loop, _manager
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

    async def _connect():
        reg = MCPServerRegistry()
        reg.register(MCPServerConfig(
            server_id="echo",
            name="Echo Server",
            transport=TransportType.STDIO,
            command=["python", "app/mcp/servers/echo_server.py"],
        ))
        manager = MCPManager(reg)
        await manager.connect_all()
        return manager

    _manager = _loop.run_until_complete(_connect())
    app.state.mcp_manager = _manager

    # Build RAG index so semantic routing works in tests
    from app.rag.indexer import tool_indexer
    all_tools = _manager.get_all_tools()
    if all_tools:
        tool_indexer.build(all_tools)
    app.state.tool_indexer = tool_indexer


def teardown_module(module):
    _loop.run_until_complete(_manager.disconnect_all())
    _loop.close()


def run(coro):
    return _loop.run_until_complete(coro)


async def _post(path, json, headers=None):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.post(path, json=json, headers=headers or HEADERS)


async def _get(path, headers=None):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.get(path, headers=headers or HEADERS)


# ── Baseline — no PHI ────────────────────────────────────────────────────────
def test_clean_input_passes_through_unchanged():
    """Non-PHI text should pass through without modification."""
    response = run(_post("/gateway/tool", json={
        "server_id":  "echo",
        "tool_name":  "echo",
        "parameters": {"text": "The weather today is sunny."},
    }))
    assert response.status_code == 200
    data = response.json()
    content = data["result"]["content"]
    assert any("The weather today is sunny." in str(c) for c in content)


# ── Input redaction ───────────────────────────────────────────────────────────
def test_person_name_redacted_in_input():
    """PERSON entity in parameters should be redacted before reaching MCP server."""
    response = run(_post("/gateway/tool", json={
        "server_id":  "echo",
        "tool_name":  "echo",
        "parameters": {"text": "Patient John Smith needs appointment"},
    }))
    assert response.status_code == 200
    content = str(response.json()["result"]["content"])
    # Echo server returns what it received — if redacted, name won't appear
    assert "John Smith" not in content
    assert "[PERSON]" in content


def test_ssn_redacted_in_input():
    """SSN in parameters should be redacted before tool call."""
    response = run(_post("/gateway/tool", json={
        "server_id":  "echo",
        "tool_name":  "echo",
        "parameters": {"text": "SSN is 123-45-6789"},
    }))
    assert response.status_code == 200
    content = str(response.json()["result"]["content"])
    assert "123-45-6789" not in content
    assert "[SSN]" in content


def test_email_redacted_in_input():
    """Email in parameters should be redacted before tool call."""
    response = run(_post("/gateway/tool", json={
        "server_id":  "echo",
        "tool_name":  "echo",
        "parameters": {"text": "Send to patient@hospital.com"},
    }))
    assert response.status_code == 200
    content = str(response.json()["result"]["content"])
    assert "patient@hospital.com" not in content
    assert "[EMAIL]" in content


def test_phone_redacted_in_input():
    """Phone number in parameters should be redacted."""
    response = run(_post("/gateway/tool", json={
        "server_id":  "echo",
        "tool_name":  "echo",
        "parameters": {"text": "Call 555-123-4567 for details"},
    }))
    assert response.status_code == 200
    content = str(response.json()["result"]["content"])
    assert "555-123-4567" not in content
    assert "[PHONE]" in content


def test_multiple_phi_types_all_redacted():
    """Multiple PHI types in one call should all be redacted."""
    response = run(_post("/gateway/tool", json={
        "server_id":  "echo",
        "tool_name":  "echo",
        "parameters": {
            "text": "Patient John Smith SSN 123-45-6789 email john@example.com"
        },
    }))
    assert response.status_code == 200
    content = str(response.json()["result"]["content"])
    assert "John Smith"      not in content
    assert "123-45-6789"     not in content
    assert "john@example.com" not in content
    assert "[PERSON]" in content
    assert "[SSN]"    in content
    assert "[EMAIL]"  in content


# ── Routing still works with PHI in parameters ────────────────────────────────
def test_tool_call_succeeds_with_phi_in_parameters():
    """Gateway should still return 200 even when PHI is detected and redacted."""
    response = run(_post("/gateway/tool", json={
        "server_id":  "echo",
        "tool_name":  "echo",
        "parameters": {"text": "Jane Doe DOB 01/15/1980"},
    }))
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["server_id"] == "echo"


def test_semantic_routing_works_with_phi_parameters():
    """Semantic routing should work even when parameters contain PHI."""
    response = run(_post("/gateway/tool", json={
        "intent":     "echo some text back",
        "parameters": {"text": "SSN 123-45-6789 for patient John Smith"},
    }))
    assert response.status_code == 200
    content = str(response.json()["result"]["content"])
    assert "123-45-6789" not in content
    assert "John Smith"  not in content


# ── Response metadata ─────────────────────────────────────────────────────────
def test_response_shape_unchanged_after_redaction():
    """Response structure should be identical with or without PHI."""
    response = run(_post("/gateway/tool", json={
        "server_id":  "echo",
        "tool_name":  "echo",
        "parameters": {"text": "John Smith"},
    }))
    assert response.status_code == 200
    data = response.json()
    assert "status"       in data
    assert "server_id"    in data
    assert "tool_name"    in data
    assert "routing_mode" in data
    assert "confidence"   in data
    assert "result"       in data


def test_ping_tool_not_affected_by_redaction():
    """Tools with no text output should not be affected by redaction."""
    response = run(_post("/gateway/tool", json={
        "server_id":  "echo",
        "tool_name":  "ping",
        "parameters": {},
    }))
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    content = str(data["result"]["content"])
    assert "pong" in content