from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from forge.db.base import Base


class RunOutbox(Base):
    """Coalesced dispatch intent. PostgreSQL truth survives missing Redis notifications."""

    __tablename__ = "run_outbox"
    __table_args__ = (Index("ix_run_outbox_due", "completed", "available_at"),)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    generation: Mapped[int] = mapped_column(default=1)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed: Mapped[bool] = mapped_column(default=False)


class RunControl(Base):
    """Cancellation can be requested without overwriting an executor's run state."""

    __tablename__ = "run_controls"
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    cancel_requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
