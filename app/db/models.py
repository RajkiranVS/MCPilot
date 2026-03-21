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