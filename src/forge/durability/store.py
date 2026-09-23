from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from forge.approvals.models import RunCheckpoint
from forge.durability.models import RunOutbox
from forge.runtime.events import record_event

BUILD = "forge-runtime-phase6-v1"
SCHEMA = 2


async def enqueue(session, run_id, available_at=None):
    """Caller commits dispatch intent with domain state; Redis is never in this transaction."""
    now = available_at or datetime.now(UTC)
    await session.execute(
        insert(RunOutbox)
        .values(run_id=run_id, generation=1, available_at=now, completed=False)
        .on_conflict_do_update(
            index_elements=[RunOutbox.run_id],
            set_={
                "generation": RunOutbox.generation + 1,
                "available_at": now,
                "published_at": None,
                "completed": False,
            },
        )
    )


async def checkpoint(session, run, state, *, due=None, terminal=False):
    record_event(session, run, "CHECKPOINT", {"phase": state["phase"], "schema": SCHEMA})
    session.add(
        RunCheckpoint(
            run_id=run.id,
            state_version=run.state_version,
            runtime_state=deepcopy(state),
            checkpoint_schema_version=SCHEMA,
            runtime_build_version=BUILD,
            last_event_sequence=run.state_version,
        )
    )
    await enqueue(session, run.id, due)
    if terminal:
        row = await session.get(RunOutbox, run.id, populate_existing=True)
        row.completed = True


async def latest(session, run_id):
    return await session.scalar(
        select(RunCheckpoint)
        .where(RunCheckpoint.run_id == run_id)
        .order_by(RunCheckpoint.state_version.desc())
        .limit(1)
    )
