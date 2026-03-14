"""
MCPilot — E2E Integration Tests
Single persistent event loop for both connection and all test calls.
Avoids Windows STDIO pipe binding issues across event loops.
"""
import asyncio
import sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from app.mcp.manager import MCPManager
from app.mcp.registry import MCPServerRegistry, MCPServerConfig, TransportType

API_KEY = "mcpilot-dev-key-001"
HEADERS = {"X-API-Key": API_KEY}

# ── Single persistent loop + manager for entire module ────────────────────────
_loop: asyncio.AbstractEventLoop | None = None
_manager: MCPManager | None = None


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


def teardown_module(module):
    async def _disconnect():
        await _manager.disconnect_all()
    _loop.run_until_complete(_disconnect())
    _loop.close()


def run(coro):
    """Run coroutine on the persistent loop — same loop MCP connected on."""
    return _loop.run_until_complete(coro)


async def _get(path, headers=None):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.get(path, headers=headers or HEADERS)


async def _post(path, json, headers=None):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.post(path, json=json, headers=headers or HEADERS)


# ── Tests ─────────────────────────────────────────────────────────────────────
def test_e2e_servers_list_shows_echo():
    response = run(_get("/gateway/servers"))
    assert response.status_code == 200
    servers = response.json()["servers"]
    assert len(servers) == 1
    assert servers[0]["server_id"] == "echo"
    assert servers[0]["connected"] is True


def test_e2e_tools_list_shows_echo_tools():
    response = run(_get("/gateway/tools"))
    assert response.status_code == 200
    data = response.json()
    tool_names = [t["name"] for t in data["tools"]]
    assert "echo" in tool_names
    assert "ping" in tool_names
    assert data["total"] == 2


def test_e2e_echo_tool_returns_input():
    response = run(_post("/gateway/tool", json={
        "server_id": "echo",
        "tool_name": "echo",
        "parameters": {"text": "MCPilot E2E test"},
    }))
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["server_id"] == "echo"
    content = data["result"]["content"]
    assert any("MCPilot E2E test" in str(c) for c in content)


def test_e2e_ping_tool_returns_pong():
    response = run(_post("/gateway/tool", json={
        "server_id": "echo",
        "tool_name": "ping",
        "parameters": {},
    }))
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    content = data["result"]["content"]
    assert any("pong" in str(c) for c in content)


def test_e2e_unknown_tool_returns_400():
    response = run(_post("/gateway/tool", json={
        "server_id": "echo",
        "tool_name": "nonexistent_tool",
        "parameters": {},
    }))
    assert response.status_code == 400


def test_e2e_unknown_server_returns_404():
    response = run(_post("/gateway/tool", json={
        "server_id": "ghost",
        "tool_name": "echo",
        "parameters": {"text": "hello"},
    }))
    assert response.status_code == 404


def test_e2e_no_auth_returns_401():
    async def _no_auth():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            return await client.post(
                "/gateway/tool",
                json={
                    "server_id": "echo",
                    "tool_name": "echo",
                    "parameters": {"text": "hello"},
                }
                # No headers argument at all
            )
    response = run(_no_auth())
    assert response.status_code == 401