"""Shared observed model health, scoped to a workspace and exact model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from forge.db.base import Base


class ModelHealth(Base):
    __tablename__ = "model_health"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    model: Mapped[str] = mapped_column(String(200), primary_key=True)
    failures: Mapped[int] = mapped_column(default=0)
    generation: Mapped[int] = mapped_column(default=0)
    state: Mapped[str] = mapped_column(String(20), default="CLOSED")
    open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    probe_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(100))
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
