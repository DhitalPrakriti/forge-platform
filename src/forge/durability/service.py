from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from forge.core.errors import DomainError
from forge.durability.models import RunControl
from forge.durability.store import BUILD, enqueue
from forge.runtime.schemas import RunCreate
from forge.runtime.service import RunService
from forge.runtime.state import TERMINAL, RunState
from forge.tools.models import Tool, ToolCall


class DurabilityService:
    def __init__(self, session):
        self.session = session
        self.runs = RunService(session)

    async def cancel(self, org, run_id):
        run = await self.runs.get(org, run_id)
        if RunState(run.status) in TERMINAL:
            return run
        if run.runtime_build_version != BUILD:
            raise DomainError(
                "LEGACY_RUN_UNSUPPORTED", "Worker control requires a Phase 6 run.", 409
            )
        await self.session.execute(
            insert(RunControl)
            .values(run_id=run.id, cancel_requested_at=datetime.now(UTC))
            .on_conflict_do_nothing()
        )
        await enqueue(self.session, run.id)
        await self.session.commit()
        return run

    async def retry(self, org, run_id, key, adapter, settings):
        run = await self.runs.get(org, run_id)
        if run.status not in {"FAILED", "TIMED_OUT"}:
            raise DomainError(
                "RUN_NOT_RETRYABLE", "Only failed or timed-out runs can be retried.", 409
            )
        unsafe = await self.session.scalar(
            select(ToolCall.id)
            .join(Tool, Tool.id == ToolCall.tool_id)
            .where(
                ToolCall.run_id == run.id,
                Tool.risk_level.in_(["MEDIUM", "HIGH"]),
                ToolCall.status.in_(["RUNNING", "COMPLETED"]),
            )
            .limit(1)
        )
        if unsafe:
            raise DomainError(
                "RETRY_REQUIRES_RECONCILIATION",
                "A side effect succeeded or has an unknown outcome; "
                "automatic repetition is blocked.",
                409,
            )
        payload = RunCreate(agent_version_id=run.agent_version_id, input=run.input)
        return await self.runs.execute(org, payload, key, adapter, settings, retry_of=run.id)
