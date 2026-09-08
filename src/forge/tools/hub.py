import asyncio
import hashlib
import json
from datetime import UTC, datetime
from time import monotonic
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from forge.runtime.events import record_event
from forge.runtime.models import Run
from forge.tools.builtins import DEFINITIONS, ToolFailure, execute_builtin
from forge.tools.models import Tool, ToolCall
from forge.tools.policy import decision
from forge.tools.repository import ToolRepository

MAX_TOOL_CALLS = 32
MAX_CALLS_PER_TURN = 8


class ToolHub:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = ToolRepository(session)

    async def execute(
        self,
        run: Run,
        model_call_id: UUID,
        call_index: int,
        request: dict,
        bound_tools: list[Tool],
        remaining_seconds: float,
    ) -> ToolCall:
        deadline = monotonic() + remaining_seconds
        name = request.get("name")
        arguments = request.get("arguments")
        name = name if isinstance(name, str) else "<invalid>"
        # JSON-compatible, bounded provider payloads only; never persist raw exceptions.
        try:
            encoded = json.dumps(
                {"name": name, "arguments": arguments}, sort_keys=True, allow_nan=False
            )
            if len(encoded.encode()) > 32_000:
                raise ValueError
        except (ValueError, TypeError):
            name, arguments = name[:200], {"invalid_payload": True}
            encoded = json.dumps({"name": name, "arguments": arguments}, sort_keys=True)
        tool = next((item for item in bound_tools if item.name == name), None)
        definition = DEFINITIONS.get(name)
        failure = None
        normalized = arguments
        if definition is None:
            failure = "TOOL_NOT_ALLOWED"
        else:
            try:
                normalized = definition.input_model.model_validate(arguments).model_dump(
                    mode="json"
                )
            except ValidationError:
                failure = "TOOL_VALIDATION_FAILED"
        if not failure and tool is None:
            failure = "TOOL_NOT_ALLOWED"
        if not failure and run.tool_calls_count >= MAX_TOOL_CALLS:
            failure = "TOOL_CALL_LIMIT_EXCEEDED"
        if not failure and remaining_seconds <= 0:
            failure = "RUN_TIMEOUT"
        request_hash = hashlib.sha256(
            json.dumps(
                {"name": name, "arguments": normalized, "tool_id": str(tool.id) if tool else None},
                sort_keys=True,
                allow_nan=False,
            ).encode()
        ).hexdigest()
        existing = await self.repository.call(model_call_id, call_index)
        if existing:
            return self.reuse(existing, request_hash)
        if run.status != "WAITING_FOR_TOOL":
            raise ToolFailure("INVALID_RUN_STATE")
        call_id = uuid4()
        call = ToolCall(
            id=call_id,
            run_id=run.id,
            model_call_id=model_call_id,
            call_index=call_index,
            tool_id=tool.id if tool else None,
            requested_name=name[:200],
            status="RUNNING",
            arguments=normalized,
            decision="DENY",
            idempotency_key=f"forge:{run.id}:{call_id}",
            request_hash=request_hash,
        )
        self.session.add(call)
        run.tool_calls_count += 1
        record_event(
            self.session,
            run,
            "TOOL_CALL_REQUESTED",
            {"tool_call_id": str(call_id), "tool_name": name[:200]},
        )
        try:
            # Stable identity is durable before any handler runs.
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if getattr(exc.orig, "sqlstate", None) != "23505":
                raise
            existing = await self.repository.call(model_call_id, call_index)
            if existing is None:
                raise
            return self.reuse(existing, request_hash)
        started = monotonic()
        call.started_at = datetime.now(UTC)
        authorized = False
        if not failure:
            try:
                # Both lock waiting and execution consume the remaining timeout.
                # Local effects are rolled back if output validation fails.
                async with self.session.begin_nested():
                    async with asyncio.timeout(
                        min(tool.timeout_seconds, max(0, deadline - monotonic()))
                    ):
                        fresh = await self.repository.tool(run.organization_id, tool.id, lock=True)
                        if fresh is None or decision(fresh, definition) != "ALLOW":
                            raise ToolFailure("POLICY_DENIED")
                        authorized = True
                        result = await execute_builtin(
                            name,
                            normalized,
                            self.session,
                            run.organization_id,
                            call.id,
                            call.idempotency_key,
                        )
                        validated = definition.output_model.model_validate(result).model_dump(
                            mode="json"
                        )
                call.result = validated
            except ValidationError:
                failure = "TOOL_OUTPUT_INVALID"
            except TimeoutError:
                failure = "TOOL_TIMEOUT"
            except ToolFailure as exc:
                failure = exc.code
            except Exception:
                failure = "TOOL_INTERNAL_ERROR"
        call.decision = "ALLOW" if authorized else "DENY"
        call.status = (
            "TIMED_OUT"
            if failure in {"TOOL_TIMEOUT", "RUN_TIMEOUT"}
            else "DENIED"
            if failure and call.decision == "DENY"
            else "FAILED"
            if failure
            else "COMPLETED"
        )
        call.error = {"code": failure} if failure else None
        call.completed_at = datetime.now(UTC)
        call.latency_ms = max(0, int((monotonic() - started) * 1000))
        record_event(
            self.session,
            run,
            "TOOL_CALL_FINISHED",
            {
                "tool_call_id": str(call.id),
                "status": call.status,
                "decision": call.decision,
                "error_code": failure,
            },
        )
        # For local demo writes, ticket + validated result + evidence commit atomically.
        await self.session.commit()
        return call

    @staticmethod
    def reuse(call: ToolCall, request_hash: str) -> ToolCall:
        if call.request_hash != request_hash:
            raise ToolFailure("TOOL_IDEMPOTENCY_CONFLICT")
        if call.status == "RUNNING":
            raise ToolFailure("TOOL_OUTCOME_UNKNOWN")
        return call
