"""
Shared test fixtures.
Unit tests: bare MCPManager, no real connections.
Integration tests: echo server connected via STDIO.
"""
import asyncio
import sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import os
os.environ["ENVIRONMENT"] = "test"
import pytest
from fastapi.testclient import TestClient
from main import app
from app.mcp.manager import MCPManager
from app.mcp.registry import MCPServerRegistry, MCPServerConfig, TransportType
from app.core.metrics import MetricsStore


@pytest.fixture(scope="module")
def client():
    """Unit test client — no MCP connections."""
    app.state.mcp_manager = MCPManager(MCPServerRegistry())
    app.state.metrics     = MetricsStore()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="module")
def integration_client():
    """
    Integration test client — echo server connected via STDIO.
    Uses the real MCPManager with a live echo server process.
    """
    reg = MCPServerRegistry()
    reg.register(MCPServerConfig(
        server_id="echo",
        name="Echo Server",
        transport=TransportType.STDIO,
        command=["python", "app/mcp/servers/echo_server.py"],
    ))
    app.state.mcp_manager = MCPManager(reg)
    app.state.metrics     = MetricsStore()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c