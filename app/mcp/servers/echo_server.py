"""
MCPilot — Echo MCP Server
Minimal MCP server for E2E integration testing.
Exposes two tools:
  - echo: returns input text unchanged
  - ping: returns a pong with timestamp
Run: python app/mcp/servers/echo_server.py
"""
from mcp.server.fastmcp import FastMCP
from datetime import datetime, timezone

mcp = FastMCP("Echo Server")


@mcp.tool()
def echo(text: str) -> str:
    """Echoes the input text back unchanged."""
    return text


@mcp.tool()
def ping() -> dict:
    """Returns a pong response with current UTC timestamp."""
    return {
        "message": "pong",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    mcp.run()