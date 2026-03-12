"""
MCPilot — MCP Registry + Manager unit tests
These test the registry and manager logic without real MCP connections.
"""
import pytest
from app.mcp.registry import MCPServerRegistry, MCPServerConfig, TransportType
from app.mcp.manager import MCPManager


def make_config(server_id="test-server") -> MCPServerConfig:
    return MCPServerConfig(
        server_id=server_id,
        name="Test Server",
        transport=TransportType.STDIO,
        command=["python", "-m", "fake_server"],
    )


# ── Registry tests ────────────────────────────────────────────────────────────
def test_registry_register_and_get():
    reg = MCPServerRegistry()
    config = make_config("srv-1")
    reg.register(config)
    assert reg.get("srv-1") is config

def test_registry_get_missing_returns_none():
    reg = MCPServerRegistry()
    assert reg.get("nonexistent") is None

def test_registry_all_returns_list():
    reg = MCPServerRegistry()
    reg.register(make_config("a"))
    reg.register(make_config("b"))
    assert len(reg.all()) == 2

def test_registry_mark_connected():
    reg = MCPServerRegistry()
    reg.register(make_config("srv-1"))
    tools = [{"name": "echo", "description": "Echoes input", "input_schema": {}}]
    reg.mark_connected("srv-1", tools)
    assert reg.get("srv-1").connected is True
    assert reg.get("srv-1").tools == tools

def test_registry_mark_disconnected():
    reg = MCPServerRegistry()
    reg.register(make_config("srv-1"))
    reg.mark_connected("srv-1", [])
    reg.mark_disconnected("srv-1")
    assert reg.get("srv-1").connected is False


# ── Manager tests ─────────────────────────────────────────────────────────────
def test_manager_list_servers_empty():
    reg = MCPServerRegistry()
    manager = MCPManager(reg)
    assert manager.list_servers() == []

def test_manager_list_servers_shows_registered():
    reg = MCPServerRegistry()
    reg.register(make_config("srv-1"))
    manager = MCPManager(reg)
    servers = manager.list_servers()
    assert len(servers) == 1
    assert servers[0]["server_id"] == "srv-1"
    assert servers[0]["connected"] is False

def test_manager_get_all_tools_empty():
    reg = MCPServerRegistry()
    manager = MCPManager(reg)
    assert manager.get_all_tools() == []

def test_manager_get_all_tools_after_connect():
    reg = MCPServerRegistry()
    reg.register(make_config("srv-1"))
    tools = [{"name": "read_file", "description": "Reads a file", "input_schema": {}}]
    reg.mark_connected("srv-1", tools)
    manager = MCPManager(reg)
    all_tools = manager.get_all_tools()
    assert len(all_tools) == 1
    assert all_tools[0]["name"] == "read_file"
    assert all_tools[0]["server_id"] == "srv-1"

@pytest.mark.asyncio
async def test_manager_call_tool_unknown_server():
    reg = MCPServerRegistry()
    manager = MCPManager(reg)
    with pytest.raises(KeyError, match="not found"):
        await manager.call_tool("ghost-server", "echo", {})