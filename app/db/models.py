"""
MCPilot — Database Models
Three tables:
  mcp_servers   → registered MCP server configs
  mcp_tools     → tool schemas discovered per server
  health_events → server connection health history
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    String, Boolean, Text, DateTime, ForeignKey,
    Integer, Float, JSON, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MCPServer(Base):
    """
    Registered MCP server configuration.
    One row per registered server — persists across restarts.
    """
    __tablename__ = "mcp_servers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    server_id:   Mapped[str]  = mapped_column(String(128), unique=True, nullable=False)
    name:        Mapped[str]  = mapped_column(String(256), nullable=False)
    transport:   Mapped[str]  = mapped_column(String(16),  nullable=False)  # stdio | sse
    command:     Mapped[str]  = mapped_column(Text,        nullable=True)   # JSON array for STDIO
    url:         Mapped[str]  = mapped_column(String(512), nullable=True)   # for SSE
    connected:   Mapped[bool] = mapped_column(Boolean,     default=False)
    enabled:     Mapped[bool] = mapped_column(Boolean,     default=True)
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    tools:         Mapped[list["MCPTool"]]       = relationship("MCPTool",       back_populates="server", cascade="all, delete-orphan")
    health_events: Mapped[list["HealthEvent"]]   = relationship("HealthEvent",   back_populates="server", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<MCPServer id={self.server_id} connected={self.connected}>"


class MCPTool(Base):
    """
    Tool schema discovered from a connected MCP server.
    Refreshed every time the server reconnects.
    """
    __tablename__ = "mcp_tools"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    server_id:    Mapped[str]  = mapped_column(String(36),  ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False)
    tool_name:    Mapped[str]  = mapped_column(String(256), nullable=False)
    description:  Mapped[str]  = mapped_column(Text,        nullable=True)
    input_schema: Mapped[dict] = mapped_column(JSON,        nullable=True)
    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    server: Mapped["MCPServer"] = relationship("MCPServer", back_populates="tools")

    __table_args__ = (
        Index("ix_mcp_tools_server_tool", "server_id", "tool_name", unique=True),
    )

    def __repr__(self) -> str:
        return f"<MCPTool server={self.server_id} tool={self.tool_name}>"


class HealthEvent(Base):
    """
    Server connection health history.
    Append-only — never updated, only inserted.
    Feeds the observability dashboard in Week 4.
    """
    __tablename__ = "health_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    server_id:    Mapped[str]   = mapped_column(String(36),  ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False)
    event_type:   Mapped[str]   = mapped_column(String(32),  nullable=False)  # connected | disconnected | error
    message:      Mapped[str]   = mapped_column(Text,        nullable=True)
    latency_ms:   Mapped[float] = mapped_column(Float,       nullable=True)
    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    server: Mapped["MCPServer"] = relationship("MCPServer", back_populates="health_events")

    __table_args__ = (
        Index("ix_health_events_server_created", "server_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<HealthEvent server={self.server_id} type={self.event_type}>"

class AuditLog(Base):
    """
    Immutable HIPAA/DPDP audit log.
    Every tool call writes one record — append-only, never updated.

    Hash chaining: each record stores SHA-256 hash of previous record's
    content, making any tampering cryptographically detectable.
    """
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    # ── Who ───────────────────────────────────────────────────────────────────
    tenant_id:      Mapped[str]  = mapped_column(String(128), nullable=False, index=True)
    client_id:      Mapped[str]  = mapped_column(String(128), nullable=False)

    # ── What ──────────────────────────────────────────────────────────────────
    server_id:      Mapped[str]  = mapped_column(String(128), nullable=False)
    tool_name:      Mapped[str]  = mapped_column(String(256), nullable=False)
    routing_mode:   Mapped[str]  = mapped_column(String(32),  nullable=True)
    session_id:     Mapped[str]  = mapped_column(String(128), nullable=True)

    # ── Compliance ────────────────────────────────────────────────────────────
    pii_in_input:   Mapped[bool] = mapped_column(Boolean, default=False)
    pii_in_output:  Mapped[bool] = mapped_column(Boolean, default=False)
    redacted_count: Mapped[int]  = mapped_column(Integer, default=0)

    # ── Outcome ───────────────────────────────────────────────────────────────
    status:         Mapped[str]  = mapped_column(String(16),  nullable=False)  # ok | error
    latency_ms:     Mapped[float]= mapped_column(Float,       nullable=True)
    error_message:  Mapped[str]  = mapped_column(Text,        nullable=True)

    # ── Tamper detection ──────────────────────────────────────────────────────
    record_hash:    Mapped[str]  = mapped_column(String(64),  nullable=False)
    prev_hash:      Mapped[str]  = mapped_column(String(64),  nullable=False, default="GENESIS")

    # ── When ──────────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_audit_log_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_log_created",        "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog tenant={self.tenant_id} "
            f"server={self.server_id} tool={self.tool_name} "
            f"pii={self.pii_in_input or self.pii_in_output}>"
        )

class DataSubject(Base):
    """
    Tracks data subjects (individuals whose PII was processed).
    Enables right-to-erasure (GDPR Article 17 / DPDP Section 12).

    When a subject requests erasure:
      1. Their pseudonym mapping is deleted
      2. Their audit records are anonymised (not deleted — audit integrity)
      3. erasure_requested_at is set for compliance evidence
    """
    __tablename__ = "data_subjects"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    # Original identifier → pseudonym mapping
    original_id:    Mapped[str] = mapped_column(String(256), nullable=False)
    pseudonym:      Mapped[str] = mapped_column(String(64),  nullable=False, unique=True)
    tenant_id:      Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # Erasure tracking
    erasure_requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    erasure_completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    erasure_status: Mapped[str] = mapped_column(
        String(32), nullable=True
    )  # pending | completed | rejected

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    __table_args__ = (
        Index("ix_data_subjects_tenant", "tenant_id"),
        Index("ix_data_subjects_pseudonym", "pseudonym"),
    )

    def __repr__(self) -> str:
        return f"<DataSubject pseudonym={self.pseudonym} tenant={self.tenant_id}>"


class RetentionPolicy(Base):
    """
    Per-tenant data retention policy configuration.
    Overrides global defaults from settings.

    DPDP Act 2023 (India) — Section 8(7):
      Data must not be retained longer than necessary.
    GDPR Article 5(1)(e):
      Storage limitation principle.
    """
    __tablename__ = "retention_policies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    tenant_id:           Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    audit_retention_days: Mapped[int] = mapped_column(Integer, default=2555)
    pii_retention_days:   Mapped[int] = mapped_column(Integer, default=365)
    auto_purge_enabled:   Mapped[bool] = mapped_column(Boolean, default=False)
    policy_version:       Mapped[str]  = mapped_column(String(16), default="1.0")
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:
        return f"<RetentionPolicy tenant={self.tenant_id} audit={self.audit_retention_days}d>"