"""
MCPilot — Integration Test Configuration
"""
import pytest
from app.mcp.manager import MCPManager
from app.mcp.registry import MCPServerRegistry, MCPServerConfig, TransportType
from app.core.metrics import MetricsStore


@pytest.fixture(scope="module")
def integration_client():
    """
    Integration test client — echo server connected via STDIO.
    """
    from main import app
    from starlette.testclient import TestClient

    reg = MCPServerRegistry()
    reg.register(MCPServerConfig(
        server_id="echo",
        name="Echo Server",
        transport=TransportType.STDIO,
        command=["python", "app/mcp/servers/echo_server.py"],
    ))
    app.state.mcp_manager = MCPManager(reg)
    app.state.metrics = MetricsStore()

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    # Force reset after integration tests
    app.state.mcp_manager = MCPManager(MCPServerRegistry())