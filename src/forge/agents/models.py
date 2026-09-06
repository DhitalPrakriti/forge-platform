from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from forge.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug"),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="status"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AgentVersion(Base):
    __tablename__ = "agent_versions"
    __table_args__ = (
        UniqueConstraint("agent_id", "version"),
        CheckConstraint(
            "lifecycle_status IN ('DRAFT','STAGING','EVALUATING','APPROVED',"
            "'PRODUCTION','DEPRECATED','ARCHIVED')",
            name="lifecycle_status",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"))
    version: Mapped[str] = mapped_column(String(100))
    goal: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str] = mapped_column(Text)
    primary_model: Mapped[str] = mapped_column(String(200))
    fallback_models: Mapped[list] = mapped_column(JSONB)
    runtime_template_revision: Mapped[str] = mapped_column(String(100))
    runtime_config: Mapped[dict] = mapped_column(JSONB)
    budget_config: Mapped[dict] = mapped_column(JSONB)
    tool_version_ids: Mapped[list] = mapped_column(JSONB)
    policy_version_ids: Mapped[list] = mapped_column(JSONB)
    evaluation_suite_version_id: Mapped[UUID | None] = mapped_column(nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(
        String(20), default="DRAFT", server_default="DRAFT"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
