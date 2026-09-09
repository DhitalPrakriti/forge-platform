from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from forge.db.base import Base


class Policy(Base):
    __tablename__ = "policies"
    __table_args__ = (UniqueConstraint("organization_id", "name", "version"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(100))
    rules: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING','APPROVED','DENIED','EXPIRED')", name="status"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    tool_call_id: Mapped[UUID] = mapped_column(ForeignKey("tool_calls.id"), unique=True)
    policy_id: Mapped[UUID] = mapped_column(ForeignKey("policies.id"))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    summary: Mapped[str] = mapped_column(Text)
    requested_payload: Mapped[dict] = mapped_column(JSONB)
    request_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class RunCheckpoint(Base):
    __tablename__ = "run_checkpoints"
    __table_args__ = (UniqueConstraint("run_id", "state_version"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"))
    state_version: Mapped[int]
    runtime_state: Mapped[dict] = mapped_column(JSONB)
    checkpoint_schema_version: Mapped[int] = mapped_column(default=1)
    runtime_build_version: Mapped[str] = mapped_column(String(100))
    last_event_sequence: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DemoRefund(Base):
    __tablename__ = "demo_refunds"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    tool_call_id: Mapped[UUID] = mapped_column(ForeignKey("tool_calls.id"), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    customer_id: Mapped[str] = mapped_column(String(100))
    amount_usd: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
