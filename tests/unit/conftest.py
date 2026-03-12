"""
Shared test fixtures for unit tests.
"""
import os
os.environ["ENVIRONMENT"] = "test"  # prevents MCP connections in lifespan

import pytest
from fastapi.testclient import TestClient
from main import app
from app.mcp.manager import MCPManager
from app.mcp.registry import MCPServerRegistry


@pytest.fixture(scope="module")
def client():
    app.state.mcp_manager = MCPManager(MCPServerRegistry())
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c