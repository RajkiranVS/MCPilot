"""
MCPilot — Root Test Configuration
Resets app.state between test modules to prevent cross-contamination.
"""
import pytest
from app.mcp.manager import MCPManager
from app.mcp.registry import MCPServerRegistry
from app.core.metrics import MetricsStore


@pytest.fixture(autouse=True, scope="module")
def reset_app_state():
    """Reset app.state before each test module to prevent shared state issues."""
    from main import app
    app.state.mcp_manager = MCPManager(MCPServerRegistry())
    app.state.metrics = MetricsStore()
    yield
    # Clean teardown
    app.state.mcp_manager = MCPManager(MCPServerRegistry())