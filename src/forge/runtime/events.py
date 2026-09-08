from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from forge.runtime.models import Run, RunEvent
from forge.runtime.state import RunState, validate_transition


def record_event(session: AsyncSession, run: Run, event_type: str, payload: dict):
    """State transitions and tool evidence share one monotonic event sequence."""
    run.state_version += 1
    run.updated_at = datetime.now(UTC)
    session.add(
        RunEvent(
            run_id=run.id, sequence_number=run.state_version, event_type=event_type, payload=payload
        )
    )


def transition_run(session: AsyncSession, run: Run, target: RunState, payload: dict | None = None):
    validate_transition(RunState(run.status), target)
    run.status = target.value
    record_event(session, run, target.value, payload or {})
