"""
MCPilot — Audit Log Writer
Convenience wrapper that wires the gateway request context
into the AuditLogRepository.

Called from gateway router after every tool call.
"""
from app.db.base import get_session_factory
from app.db.repository import AuditLogRepository
from app.core.logging import get_logger

logger = get_logger(__name__)


async def write_audit_record(
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
) -> None:
    """
    Write an immutable audit record to PostgreSQL.
    Fire-and-forget — failures are logged but never raise to caller.
    """
    try:
        factory = get_session_factory()
        async with factory() as session:
            repo = AuditLogRepository(session)
            await repo.write(
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
            )
            await session.commit()
    except Exception as e:
        logger.error(f"Audit log write failed: {e}")