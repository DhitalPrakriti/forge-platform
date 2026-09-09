from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from forge.db.base import Base


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key"),
        CheckConstraint(
            "status IN ('CREATED','QUEUED','RUNNING','WAITING_FOR_TOOL',"
            "'WAITING_FOR_APPROVAL','RETRYING','COMPLETED','FAILED','CANCELLED','TIMED_OUT')",
            name="status",
        ),
        Index("ix_runs_agent_created", "agent_id", "created_at"),
        Index("ix_runs_status_created", "status", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    retry_of_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"))
    agent_version_id: Mapped[UUID] = mapped_column(ForeignKey("agent_versions.id"))
    status: Mapped[str] = mapped_column(String(30))
    state_version: Mapped[int] = mapped_column(default=0)
    input: Mapped[dict] = mapped_column(JSONB)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_step: Mapped[int] = mapped_column(default=0)
    model_calls_count: Mapped[int] = mapped_column(default=0)
    tool_calls_count: Mapped[int] = mapped_column(default=0)
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    runtime_build_version: Mapped[str] = mapped_column(String(100))
    execution_config: Mapped[dict] = mapped_column(JSONB)
    idempotency_key: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __mapper_args__ = {"version_id_col": state_version, "version_id_generator": False}


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (UniqueConstraint("run_id", "sequence_number"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"))
    sequence_number: Mapped[int]
    event_type: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelCall(Base):
    __tablename__ = "model_calls"
    __table_args__ = (Index("ix_model_calls_run_created", "run_id", "created_at"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"))
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(200))
    actual_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)
    usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
