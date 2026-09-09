from datetime import UTC, datetime
from importlib.metadata import version as package_version
from uuid import UUID

from sqlalchemy import select

from forge.approvals.models import Approval, RunCheckpoint
from forge.approvals.policy import resolve_policy
from forge.core.errors import DomainError
from forge.model_router.base import ModelRequest
from forge.runtime.checkpoints import load_exchanges, load_result
from forge.runtime.engine import RuntimeEngine
from forge.runtime.events import record_event, transition_run
from forge.runtime.models import ModelCall, Run
from forge.runtime.service import RunService
from forge.runtime.state import TERMINAL, RunState
from forge.tools.models import ToolCall
from forge.tools.registry import ToolRegistry
from forge.tools.repository import ToolRepository


class ApprovalService:
    def __init__(self, session):
        self.session = session

    async def get(self, org, approval_id):
        approval = await self.session.scalar(
            select(Approval).where(Approval.id == approval_id, Approval.organization_id == org)
        )
        if approval is None:
            raise DomainError("APPROVAL_NOT_FOUND", "Approval not found.", 404)
        return approval

    async def locked_run(self, org, run_id):
        run = await self.session.scalar(
            select(Run)
            .where(Run.id == run_id, Run.organization_id == org)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if run is None:
            raise DomainError("RUN_NOT_FOUND", "Run not found.", 404)
        return run

    async def cancel(self, run, approval, code):
        run.completed_at, run.error_code = datetime.now(UTC), code
        call = await self.session.get(ToolCall, approval.tool_call_id)
        call.status, call.error, call.completed_at = "DENIED", {"code": code}, run.completed_at
        record_event(
            self.session,
            run,
            "TOOL_CALL_FINISHED",
            {"tool_call_id": str(call.id), "status": "DENIED", "error_code": code},
        )
        transition_run(self.session, run, RunState.CANCELLED, {"reason": code})

    async def decide(self, org, approval_id, verdict, reason, reviewer):
        approval = await self.get(org, approval_id)
        run = await self.locked_run(org, approval.run_id)
        await self.session.refresh(approval)
        if approval.status == verdict:
            return approval
        if approval.status != "PENDING" or run.status != "WAITING_FOR_APPROVAL":
            raise DomainError("APPROVAL_ALREADY_DECIDED", "Approval is no longer pending.", 409)
        now = datetime.now(UTC)
        if approval.expires_at <= now:
            approval.status = "EXPIRED"
            await self.cancel(run, approval, "APPROVAL_EXPIRED")
        else:
            approval.status = verdict
            approval.reviewed_by, approval.reviewed_at = reviewer, now
            approval.decision_reason = reason
            record_event(
                self.session,
                run,
                "APPROVAL_DECIDED",
                {
                    "approval_id": str(approval.id),
                    "decision": verdict,
                    "reviewed_by": str(reviewer),
                },
            )
            if verdict == "DENIED":
                await self.cancel(run, approval, "APPROVAL_DENIED")
            else:
                # Durable intent; explicit resume is safely repeatable after process restart.
                record_event(
                    self.session, run, "RESUME_REQUESTED", {"approval_id": str(approval.id)}
                )
        await self.session.commit()
        return approval

    async def resume(self, org, run_id, adapter):
        run = await self.locked_run(org, run_id)
        if RunState(run.status) in TERMINAL:
            return run
        if run.status != "WAITING_FOR_APPROVAL":
            raise DomainError("RUN_NOT_WAITING", "Run is not waiting for approval.", 409)
        approval = await self.session.scalar(
            select(Approval)
            .where(Approval.run_id == run.id)
            .order_by(Approval.requested_at.desc())
            .limit(1)
        )
        if approval is None:
            raise DomainError("APPROVAL_NOT_FOUND", "Waiting approval is missing.", 409)
        if approval.expires_at <= datetime.now(UTC):
            # Preserve an already-recorded human decision; its authority has expired.
            if approval.status == "PENDING":
                approval.status = "EXPIRED"
            await self.cancel(run, approval, "APPROVAL_EXPIRED")
            await self.session.commit()
            return run
        if approval.status != "APPROVED":
            raise DomainError(
                "APPROVAL_REQUIRED", "An approved, unexpired decision is required.", 409
            )
        checkpoint = await self.session.scalar(
            select(RunCheckpoint)
            .where(RunCheckpoint.run_id == run.id)
            .order_by(RunCheckpoint.state_version.desc())
            .limit(1)
        )
        if (
            checkpoint is None
            or checkpoint.checkpoint_schema_version != 1
            or checkpoint.runtime_build_version != "forge-runtime-phase5-v1"
            or run.runtime_build_version != checkpoint.runtime_build_version
        ):
            raise DomainError(
                "CHECKPOINT_INCOMPATIBLE", "Continuation is incompatible with this runtime.", 409
            )
        if adapter.provider == "google" and run.execution_config.get(
            "provider_sdk_version"
        ) != package_version("google-genai"):
            raise DomainError(
                "CHECKPOINT_INCOMPATIBLE", "Resume requires the original provider SDK version.", 409
            )
        try:
            load_result(checkpoint.runtime_state["result"])
            load_exchanges(checkpoint.runtime_state["exchanges"])
        except (ValueError, TypeError, KeyError):
            raise DomainError(
                "CHECKPOINT_INCOMPATIBLE", "Saved continuation cannot be decoded.", 409
            ) from None
        version, _ = await RunService(self.session).repository.version(org, run.agent_version_id)
        tools = await ToolRegistry(self.session).resolve(org, version.tool_version_ids)
        if set(await ToolRepository(self.session).bindings(version.id)) != {t.id for t in tools}:
            raise DomainError("TOOL_BINDING_INVALID", "Pinned tool bindings differ.", 409)
        await resolve_policy(self.session, org, version.policy_version_ids, required=True)
        if adapter.provider != run.execution_config["provider"]:
            raise DomainError(
                "CHECKPOINT_INCOMPATIBLE", "Resume requires the original provider.", 409
            )
        adapter.validate(version.primary_model)
        config = run.execution_config
        request = ModelRequest(
            model=version.primary_model,
            goal=version.goal,
            instructions=version.instructions,
            message=run.input["message"],
            timeout_seconds=config["timeout_seconds"],
            max_output_tokens=config["max_output_tokens"],
            tools=[
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ],
        )
        call = await self.session.get(ModelCall, UUID(checkpoint.runtime_state["model_call_id"]))
        if (
            call is None
            or call.run_id != run.id
            or checkpoint.runtime_state["step"] != run.current_step
        ):
            raise DomainError(
                "CHECKPOINT_INCOMPATIBLE", "Continuation does not match the run.", 409
            )
        transition_run(self.session, run, RunState.RUNNING, {"checkpoint_id": str(checkpoint.id)})
        # Claim before releasing the lock: concurrent resume cannot become another executor.
        await self.session.commit()
        failure = await RuntimeEngine(self.session).execute(
            run,
            call,
            adapter,
            request,
            tools,
            version.runtime_config["max_steps"],
            version.runtime_config["max_runtime_seconds"],
            continuation=checkpoint.runtime_state,
        )
        if run.status != "WAITING_FOR_APPROVAL":
            run.completed_at, run.error_code = datetime.now(UTC), failure
            target = (
                RunState.TIMED_OUT
                if failure in {"MODEL_TIMEOUT", "TOOL_TIMEOUT", "RUN_TIMEOUT"}
                else RunState.FAILED
                if failure
                else RunState.COMPLETED
            )
            transition_run(self.session, run, target, {"error_code": failure})
            await self.session.commit()
        return run
