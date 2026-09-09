from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from forge.db.base import Base


class Tool(Base):
    __tablename__ = "tools"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", "version"),
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="status"),
        CheckConstraint("risk_level IN ('LOW','MEDIUM','HIGH')", name="risk_level"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    input_schema: Mapped[dict] = mapped_column(JSONB)
    output_schema: Mapped[dict] = mapped_column(JSONB)
    risk_level: Mapped[str] = mapped_column(String(20))
    timeout_seconds: Mapped[int]
    retry_safe: Mapped[bool]
    idempotency_supported: Mapped[bool]
    handler_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentTool(Base):
    __tablename__ = "agent_tools"
    agent_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_versions.id"), primary_key=True
    )
    tool_id: Mapped[UUID] = mapped_column(ForeignKey("tools.id"), primary_key=True)


class ToolCall(Base):
    __tablename__ = "tool_calls"
    __table_args__ = (
        UniqueConstraint("model_call_id", "call_index"),
        CheckConstraint(
            "status IN ('WAITING_FOR_APPROVAL','RUNNING','COMPLETED',"
            "'DENIED','FAILED','TIMED_OUT')",
            name="status",
        ),
        Index("ix_tool_calls_run_created", "run_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"))
    model_call_id: Mapped[UUID] = mapped_column(ForeignKey("model_calls.id"))
    call_index: Mapped[int]
    tool_id: Mapped[UUID | None] = mapped_column(ForeignKey("tools.id"), nullable=True)
    requested_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30))
    arguments: Mapped[Any] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    decision: Mapped[str] = mapped_column(String(30))
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DemoTicket(Base):
    """A local-only side effect, never an external helpdesk integration."""

    __tablename__ = "demo_tickets"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    tool_call_id: Mapped[UUID] = mapped_column(ForeignKey("tool_calls.id"), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    customer_id: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(200))
    details: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
