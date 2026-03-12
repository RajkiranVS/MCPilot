"""
MCPilot — MCP Client Wrapper
One instance per upstream MCP server.
Wraps the MCP Python SDK and handles connect/disconnect lifecycle.

Transport selection (from your MCP notes):
  STDIO → local/on-premise servers  (subprocess)
  SSE   → remote servers            (HTTP)
"""
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.sse import sse_client
from app.mcp.registry import MCPServerConfig, TransportType
from app.core.logging import get_logger

logger = get_logger(__name__)


class MCPClient:
    """
    Manages a single MCP client session to one upstream server.
    Call connect() before invoking tools.
    Call disconnect() on shutdown.
    """

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._session: ClientSession | None = None
        self._ctx = None

    @property
    def is_connected(self) -> bool:
        return self._session is not None

    async def connect(self) -> list[dict]:
        """
        Open transport + initialise MCP session.
        Returns list of tool schemas advertised by the server.
        """
        logger.info(
            f"Connecting to MCP server | id={self.config.server_id} "
            f"transport={self.config.transport}"
        )

        if self.config.transport == TransportType.STDIO:
            server_params = StdioServerParameters(
                command=self.config.command[0],
                args=self.config.command[1:],
            )
            self._ctx = stdio_client(server_params)

        elif self.config.transport == TransportType.SSE:
            self._ctx = sse_client(self.config.url)

        else:
            raise ValueError(f"Unknown transport: {self.config.transport}")

        read, write = await self._ctx.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()

        # Discover tools advertised by this server
        tools_result = await self._session.list_tools()
        tool_schemas = [
            {
                "name":        t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema,
            }
            for t in tools_result.tools
        ]

        logger.info(
            f"Connected | id={self.config.server_id} "
            f"tools={[t['name'] for t in tool_schemas]}"
        )
        return tool_schemas

    async def call_tool(self, tool_name: str, parameters: dict) -> dict:
        """
        Invoke a tool on this MCP server.
        Raises RuntimeError if not connected.
        Raises ValueError if tool not found.
        """
        if not self._session:
            raise RuntimeError(
                f"Client not connected: {self.config.server_id}"
            )

        known = {t["name"] for t in self.config.tools}
        if tool_name not in known:
            raise ValueError(
                f"Tool '{tool_name}' not found on server "
                f"'{self.config.server_id}'. Available: {sorted(known)}"
            )

        logger.info(
            f"Calling tool | server={self.config.server_id} "
            f"tool={tool_name} params={list(parameters.keys())}"
        )

        result = await self._session.call_tool(tool_name, parameters)

        # Normalise MCP result into a plain dict
        content = []
        for block in result.content:
            if hasattr(block, "text"):
                content.append({"type": "text", "text": block.text})
            else:
                content.append({"type": "unknown", "raw": str(block)})

        return {
            "content":   content,
            "is_error":  result.isError or False,
        }

    async def disconnect(self) -> None:
        """Close session and transport cleanly."""
        if self._session:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
            self._session = None

        if self._ctx:
            try:
                await self._ctx.__aexit__(None, None, None)
            except Exception:
                pass
            self._ctx = None

        logger.info(f"Disconnected | id={self.config.server_id}")