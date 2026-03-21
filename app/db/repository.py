"""
MCPilot — Tool Registry Repository
Data access layer for MCP server and tool schema persistence.
All database operations go through this class — no raw SQL in routers.
"""
import json
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.db.models import MCPServer, MCPTool, HealthEvent
from app.core.logging import get_logger

logger = get_logger(__name__)


class ToolRegistryRepository:
    """
    Handles all CRUD for MCP server configs, tool schemas,
    and health events.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    # ── Server operations ─────────────────────────────────────────────────────

    async def upsert_server(
        self,
        server_id:  str,
        name:       str,
        transport:  str,
        command:    list[str] | None = None,
        url:        str | None = None,
    ) -> MCPServer:
        """
        Insert or update a server config.
        Called at startup when servers are registered.
        """
        result = await self._session.execute(
            select(MCPServer).where(MCPServer.server_id == server_id)
        )
        server = result.scalar_one_or_none()

        if server is None:
            server = MCPServer(
                server_id=server_id,
                name=name,
                transport=transport,
                command=json.dumps(command) if command else None,
                url=url,
            )
            self._session.add(server)
            logger.info(f"Server registered in DB | id={server_id}")
        else:
            server.name      = name
            server.transport = transport
            server.command   = json.dumps(command) if command else None
            server.url       = url
            logger.debug(f"Server updated in DB | id={server_id}")

        await self._session.flush()
        return server

    async def set_server_connected(
        self,
        server_id: str,
        connected: bool,
    ) -> None:
        """Update connection status after connect/disconnect."""
        await self._session.execute(
            update(MCPServer)
            .where(MCPServer.server_id == server_id)
            .values(connected=connected)
        )

    async def get_server(self, server_id: str) -> MCPServer | None:
        result = await self._session.execute(
            select(MCPServer)
            .where(MCPServer.server_id == server_id)
            .options(selectinload(MCPServer.tools))
        )
        return result.scalar_one_or_none()

    async def list_servers(self) -> list[MCPServer]:
        result = await self._session.execute(
            select(MCPServer)
            .where(MCPServer.enabled == True)
            .options(selectinload(MCPServer.tools))
            .order_by(MCPServer.created_at)
        )
        return list(result.scalars().all())

    # ── Tool operations ───────────────────────────────────────────────────────
    async def sync_tools(
        self,
        server: MCPServer,
        tools:  list[dict],
    ) -> None:
        """
        Replace all tool schemas for a server with fresh discovery results.
        Called every time a server reconnects.
        """
        # Delete existing tools for this server
        existing = await self._session.execute(
            select(MCPTool).where(MCPTool.server_id == server.id)
        )
        for tool in existing.scalars().all():
            await self._session.delete(tool)

        # Flush deletes to DB before inserting — prevents unique constraint violation
        await self._session.flush()

        # Insert fresh tool schemas
        for tool_dict in tools:
            tool = MCPTool(
                server_id=server.id,
                tool_name=tool_dict["name"],
                description=tool_dict.get("description", ""),
                input_schema=tool_dict.get("input_schema", {}),
            )
            self._session.add(tool)

        logger.info(
            f"Tools synced | server={server.server_id} count={len(tools)}"
        )
        
    async def list_all_tools(self) -> list[dict]:
        """
        Returns flat list of all tools across all connected servers.
        Used to rebuild the RAG index after DB sync.
        """
        result = await self._session.execute(
            select(MCPTool, MCPServer.server_id.label("srv_id"))
            .join(MCPServer, MCPTool.server_id == MCPServer.id)
            .where(MCPServer.connected == True)
        )
        rows = result.all()
        return [
            {
                "server_id":    row.srv_id,
                "name":         row.MCPTool.tool_name,
                "description":  row.MCPTool.description or "",
                "input_schema": row.MCPTool.input_schema or {},
            }
            for row in rows
        ]

    # ── Health events ─────────────────────────────────────────────────────────

    async def record_health_event(
        self,
        server:     MCPServer,
        event_type: str,
        message:    str | None = None,
        latency_ms: float | None = None,
    ) -> None:
        """
        Append a health event. Never updates existing records.
        """
        event = HealthEvent(
            server_id=server.id,
            event_type=event_type,
            message=message,
            latency_ms=latency_ms,
        )
        self._session.add(event)
        logger.debug(
            f"Health event | server={server.server_id} type={event_type}"
        )

    async def list_health_events(
        self,
        server_id: str,
        limit:     int = 50,
    ) -> list[HealthEvent]:
        server = await self.get_server(server_id)
        if not server:
            return []
        result = await self._session.execute(
            select(HealthEvent)
            .where(HealthEvent.server_id == server.id)
            .order_by(HealthEvent.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())