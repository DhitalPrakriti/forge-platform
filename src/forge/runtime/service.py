import hashlib
import json
from datetime import UTC, datetime
from importlib.metadata import version as package_version
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from forge.approvals.policy import resolve_policy
from forge.core.config import Settings
from forge.core.errors import DomainError
from forge.model_router.base import ModelAdapter, ModelRequest
from forge.runtime.engine import RuntimeEngine
from forge.runtime.events import transition_run
from forge.runtime.models import ModelCall, Run, RunEvent
from forge.runtime.repository import RunRepository
from forge.runtime.schemas import RunCreate
from forge.runtime.state import RunState
from forge.tools.hub import MAX_CALLS_PER_TURN, MAX_TOOL_CALLS
from forge.tools.registry import ToolRegistry
from forge.tools.repository import ToolRepository


class RunService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = RunRepository(session)

    async def get(self, organization_id: UUID, run_id: UUID) -> Run:
        run = await self.repository.run(organization_id, run_id)
        if run is None:
            raise DomainError("RUN_NOT_FOUND", "Run not found.", 404)
        return run

    async def events(self, organization_id: UUID, run_id: UUID, after: int, limit: int):
        await self.get(organization_id, run_id)
        return await self.repository.events(run_id, after, limit)

    async def calls(self, organization_id: UUID, run_id: UUID):
        await self.get(organization_id, run_id)
        return await self.repository.calls(run_id)

    def transition(self, run: Run, target: RunState, payload: dict | None = None):
        transition_run(self.session, run, target, payload)

    @staticmethod
    def replay(existing: Run, request_hash: str) -> tuple[Run, bool]:
        if existing.request_hash != request_hash:
            raise DomainError(
                "IDEMPOTENCY_CONFLICT", "Key already belongs to another request.", 409
            )
        # A duplicate never becomes another executor, even when the existing run is unfinished.
        return existing, False

    async def execute(
        self,
        organization_id: UUID,
        payload: RunCreate,
        key: str,
        adapter: ModelAdapter,
        settings: Settings,
    ) -> tuple[Run, bool]:
        request_hash = hashlib.sha256(
            json.dumps(payload.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()
        existing = await self.repository.by_key(organization_id, key)
        if existing:
            return self.replay(existing, request_hash)
        row = await self.repository.version(organization_id, payload.agent_version_id)
        if row is None:
            raise DomainError("VERSION_NOT_FOUND", "Version not found.", 404)
        version, agent_status = row
        if agent_status != "ACTIVE" or version.lifecycle_status not in ("DRAFT", "STAGING"):
            raise DomainError(
                "VERSION_NOT_RUNNABLE", "Use an active agent's DRAFT or STAGING version.", 409
            )
        if version.fallback_models or version.runtime_template_revision != "standard-agent-v1":
            raise DomainError(
                "RUNTIME_CONFIGURATION_UNSUPPORTED",
                "Phase 5 supports standard-agent-v1 without fallback.",
                409,
            )
        tools = await ToolRegistry(self.session).resolve(organization_id, version.tool_version_ids)
        await resolve_policy(
            self.session,
            organization_id,
            version.policy_version_ids,
            required=any(t.name == "issue_refund" for t in tools),
        )
        bindings = await ToolRepository(self.session).bindings(version.id)
        if set(bindings) != {tool.id for tool in tools}:
            raise DomainError(
                "TOOL_BINDING_INVALID", "Tool bindings do not match the immutable version.", 409
            )
        adapter.validate(version.primary_model)
        timeout = min(settings.model_timeout_seconds, version.runtime_config["max_runtime_seconds"])
        request = ModelRequest(
            model=version.primary_model,
            goal=version.goal,
            instructions=version.instructions,
            message=payload.input.message,
            timeout_seconds=timeout,
            max_output_tokens=settings.model_max_output_tokens,
            tools=[
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
                for tool in tools
            ],
        )
        run = Run(
            organization_id=organization_id,
            agent_id=version.agent_id,
            agent_version_id=version.id,
            status=RunState.CREATED.value,
            state_version=0,
            input=payload.input.model_dump(),
            runtime_build_version="forge-runtime-phase5-v1",
            idempotency_key=key,
            request_hash=request_hash,
            execution_config={
                "provider": adapter.provider,
                "tool_version_ids": [str(tool.id) for tool in tools],
                "max_tool_calls": MAX_TOOL_CALLS,
                "max_calls_per_turn": MAX_CALLS_PER_TURN,
                "policy_boundary": "DETERMINISTIC_REFUND_V1",
                "policy_version_ids": version.policy_version_ids,
                "max_runtime_seconds": version.runtime_config["max_runtime_seconds"],
                "requested_model": request.model,
                "timeout_seconds": timeout,
                "max_output_tokens": request.max_output_tokens,
                "runtime_template_revision": version.runtime_template_revision,
                "budget_enforcement": "DEFERRED_TO_PHASE_7",
                "provider_sdk_version": package_version("google-genai")
                if adapter.provider == "google"
                else None,
            },
        )
        self.session.add(run)
        try:
            await self.session.flush()
            self.session.add(
                RunEvent(run_id=run.id, sequence_number=0, event_type="CREATED", payload={})
            )
            self.transition(run, RunState.RUNNING)
            run.started_at = datetime.now(UTC)
            run.current_step = 1
            run.model_calls_count = 1
            call = ModelCall(
                run_id=run.id, provider=adapter.provider, model=request.model, status="RUNNING"
            )
            self.session.add(call)
            # Persist execution intent and release all row locks before contacting the provider.
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if getattr(exc.orig, "sqlstate", None) != "23505":
                raise
            existing = await self.repository.by_key(organization_id, key)
            if existing is None:
                raise
            return self.replay(existing, request_hash)

        failure = await RuntimeEngine(self.session).execute(
            run,
            call,
            adapter,
            request,
            tools,
            version.runtime_config["max_steps"],
            version.runtime_config["max_runtime_seconds"],
        )
        if run.status == RunState.WAITING_FOR_APPROVAL:
            return run, True
        run.completed_at = datetime.now(UTC)
        run.error_code = failure
        target = (
            RunState.TIMED_OUT
            if failure in {"MODEL_TIMEOUT", "TOOL_TIMEOUT", "RUN_TIMEOUT"}
            else (RunState.FAILED if failure else RunState.COMPLETED)
        )
        self.transition(run, target, {"error_code": failure})
        try:
            # Completed model-call evidence and terminal state/event commit together.
            await self.session.commit()
        except StaleDataError as exc:
            await self.session.rollback()
            raise DomainError("INVALID_RUN_STATE", "Run state changed concurrently.", 409) from exc
        return run, True
