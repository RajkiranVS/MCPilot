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
import hashlib
from app.db.models import MCPServer, MCPTool, HealthEvent, AuditLog

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

class AuditLogRepository:
    """
    Append-only audit log writer.
    Every write computes a SHA-256 hash chain for tamper detection.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    def _compute_hash(self, record: AuditLog) -> str:
        """
        Compute SHA-256 hash of record content.
        Uses id + business fields — avoids timestamp precision issues.
        """
        content = (
            f"{record.id}|"
            f"{record.tenant_id}|{record.client_id}|"
            f"{record.server_id}|{record.tool_name}|"
            f"{record.pii_in_input}|{record.pii_in_output}|"
            f"{record.redacted_count}|{record.status}|"
            f"{record.prev_hash}"
        )
        return hashlib.sha256(content.encode()).hexdigest()

    async def write(
        self,
        tenant_id:      str,
        client_id:      str,
        server_id:      str,
        tool_name:      str,
        routing_mode:   str   = "explicit",
        session_id:     str   | None = None,
        pii_in_input:   bool  = False,
        pii_in_output:  bool  = False,
        redacted_count: int   = 0,
        status:         str   = "ok",
        latency_ms:     float | None = None,
        error_message:  str   | None = None,
    ) -> AuditLog:
        """
        Write one immutable audit record.
        Automatically chains to the previous record's hash.
        """
        # Get the hash of the most recent record for chaining
        result = await self._session.execute(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        last = result.scalar_one_or_none()
        prev_hash = last.record_hash if last else "GENESIS"

        record = AuditLog(
            tenant_id=tenant_id,
            client_id=client_id,
            server_id=server_id,
            tool_name=tool_name,
            routing_mode=routing_mode,
            session_id=session_id,
            pii_in_input=pii_in_input,
            pii_in_output=pii_in_output,
            redacted_count=redacted_count,
            status=status,
            latency_ms=latency_ms,
            error_message=error_message,
            prev_hash=prev_hash,
            record_hash="pending",  # computed after ID is set
        )
        self._session.add(record)
        await self._session.flush()  # gets the ID assigned

        # Now compute hash with all fields populated
        record.record_hash = self._compute_hash(record)
        await self._session.flush()

        logger.info(
            f"Audit record written | tenant={tenant_id} "
            f"server={server_id} tool={tool_name} "
            f"pii={pii_in_input or pii_in_output} "
            f"status={status}"
        )
        return record

    async def list_recent(
        self,
        tenant_id: str | None = None,
        limit:     int = 50,
    ) -> list[AuditLog]:
        """List recent audit records, optionally filtered by tenant."""
        query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        if tenant_id:
            query = query.where(AuditLog.tenant_id == tenant_id)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def verify_chain(self, limit: int = 100) -> dict:
        """
        Verify the hash chain integrity.
        Returns dict with is_valid bool and any broken links found.
        """
        result = await self._session.execute(
            select(AuditLog)
            .order_by(AuditLog.created_at.asc())
            .limit(limit)
        )
        records = list(result.scalars().all())

        broken = []
        for i, record in enumerate(records):
            expected_hash = self._compute_hash(record)
            if record.record_hash != expected_hash:
                broken.append({
                    "id":       record.id,
                    "position": i,
                    "expected": expected_hash,
                    "actual":   record.record_hash,
                })

        return {
            "is_valid":      len(broken) == 0,
            "records_checked": len(records),
            "broken_links":  broken,
        }