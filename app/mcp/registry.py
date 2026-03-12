"""
MCPilot — MCP Server Registry
In-memory registry of all connected MCP servers.
Replaced by PostgreSQL in BUILD-007.

Each entry describes one upstream MCP server:
  - server_id: unique identifier used in tool call routing
  - transport: "stdio" (local) or "sse" (remote)
  - command/url: how to reach the server
  - tools: list of tool schemas discovered at connect time
"""
from dataclasses import dataclass, field
from enum import Enum


class TransportType(str, Enum):
    STDIO = "stdio"
    SSE   = "sse"


@dataclass
class MCPServerConfig:
    server_id:   str
    name:        str
    transport:   TransportType
    # STDIO transport
    command:     list[str] = field(default_factory=list)
    # SSE transport
    url:         str = ""
    # Populated after connection
    tools:       list[dict] = field(default_factory=list)
    connected:   bool = False


class MCPServerRegistry:
    """
    Singleton registry — holds all server configs.
    Manager reads from here when opening clients.
    """
    def __init__(self):
        self._servers: dict[str, MCPServerConfig] = {}

    def register(self, config: MCPServerConfig) -> None:
        self._servers[config.server_id] = config

    def get(self, server_id: str) -> MCPServerConfig | None:
        return self._servers.get(server_id)

    def all(self) -> list[MCPServerConfig]:
        return list(self._servers.values())

    def mark_connected(self, server_id: str, tools: list[dict]) -> None:
        server = self._servers.get(server_id)
        if server:
            server.tools = tools
            server.connected = True

    def mark_disconnected(self, server_id: str) -> None:
        server = self._servers.get(server_id)
        if server:
            server.connected = False


# Module-level singleton
registry = MCPServerRegistry()