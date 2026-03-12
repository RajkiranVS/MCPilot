"""
MCPilot — MCP Manager
Orchestrates all MCP clients.
This is MCPilot's core routing engine — the "gateway" in the gateway.

Responsibilities:
  - Boot: connect to all registered servers at startup
  - Route: given a server_id, find the right client and call the tool
  - Shutdown: disconnect all clients cleanly
  - Introspect: expose server + tool metadata for RAG indexing (Week 2)
"""
from app.mcp.client import MCPClient
from app.mcp.registry import MCPServerConfig, MCPServerRegistry, registry
from app.core.logging import get_logger

logger = get_logger(__name__)


class MCPManager:
    """
    Holds a pool of MCPClients — one per registered server.
    Injected into FastAPI app state at startup.
    """

    def __init__(self, reg: MCPServerRegistry = registry):
        self._registry = reg
        self._clients: dict[str, MCPClient] = {}

    async def connect_all(self) -> None:
        """Connect to every server in the registry. Called at app startup."""
        for config in self._registry.all():
            await self._connect_one(config)

    async def _connect_one(self, config: MCPServerConfig) -> None:
        client = MCPClient(config)
        try:
            tools = await client.connect()
            self._registry.mark_connected(config.server_id, tools)
            self._clients[config.server_id] = client
        except Exception as e:
            logger.error(
                f"Failed to connect to MCP server | "
                f"id={config.server_id} error={e}"
            )
            self._registry.mark_disconnected(config.server_id)

    async def disconnect_all(self) -> None:
        """Disconnect all clients cleanly. Called at app shutdown."""
        for client in self._clients.values():
            await client.disconnect()
        self._clients.clear()

    async def call_tool(
        self,
        server_id: str,
        tool_name: str,
        parameters: dict,
    ) -> dict:
        """
        Route a tool call to the correct MCP client.
        Raises KeyError if server not found.
        Raises RuntimeError if server not connected.
        """
        client = self._clients.get(server_id)
        if not client:
            available = list(self._clients.keys())
            raise KeyError(
                f"Server '{server_id}' not found or not connected. "
                f"Available: {available}"
            )
        return await client.call_tool(tool_name, parameters)

    def list_servers(self) -> list[dict]:
        """
        Returns metadata for all registered servers.
        Used by GET /gateway/servers and Week 2 RAG indexing.
        """
        return [
            {
                "server_id":  s.server_id,
                "name":       s.name,
                "transport":  s.transport,
                "connected":  s.connected,
                "tool_count": len(s.tools),
                "tools":      s.tools,
            }
            for s in self._registry.all()
        ]

    def get_all_tools(self) -> list[dict]:
        """
        Returns flat list of all tools across all servers.
        Week 2: fed directly into LlamaIndex for RAG tool indexing.
        """
        tools = []
        for s in self._registry.all():
            for t in s.tools:
                tools.append({**t, "server_id": s.server_id})
        return tools


# Module-level singleton — shared across the app via app.state
mcp_manager = MCPManager()