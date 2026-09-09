import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from time import monotonic

from sqlalchemy.ext.asyncio import AsyncSession

from forge.approvals.models import RunCheckpoint
from forge.model_router.base import (
    ModelAdapter,
    ModelFailure,
    ModelRequest,
    ModelResult,
    ToolExchange,
)
from forge.runtime.checkpoints import load_exchanges, load_result, save_exchanges, save_result
from forge.runtime.events import record_event, transition_run
from forge.runtime.models import ModelCall, Run
from forge.runtime.state import RunState
from forge.tools.builtins import ToolFailure
from forge.tools.hub import MAX_CALLS_PER_TURN, MAX_TOOL_CALLS, ToolHub
from forge.tools.models import Tool


class RuntimeEngine:
    """Bounded model/tool loop with approval continuation. General recovery is Phase 6."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.hub = ToolHub(session)

    async def model_step(
        self, run: Run, call: ModelCall, adapter: ModelAdapter, request: ModelRequest
    ) -> tuple[ModelResult | None, str | None]:
        started = monotonic()
        result, failure = None, None
        try:
            async with asyncio.timeout(request.timeout_seconds):
                result = await adapter.generate(request)
            call.actual_model = result.actual_model
            call.input_tokens = result.input_tokens
            call.output_tokens = result.output_tokens
            call.usage = result.usage
            call.status = "COMPLETED"
            if adapter.provider == "fake":
                call.estimated_cost = run.total_cost = Decimal("0")
        except (TimeoutError, ModelFailure) as exc:
            failure = "MODEL_TIMEOUT" if isinstance(exc, TimeoutError) else exc.code
            call.status = "TIMED_OUT" if failure == "MODEL_TIMEOUT" else "FAILED"
            call.error_type = failure
        except Exception:
            failure = "MODEL_INTERNAL_ERROR"
            call.status = "FAILED"
            call.error_type = failure
        call.latency_ms = max(0, int((monotonic() - started) * 1000))
        call.completed_at = datetime.now(UTC)
        return result, failure

    async def execute(
        self,
        run: Run,
        call: ModelCall,
        adapter: ModelAdapter,
        request: ModelRequest,
        tools: list[Tool],
        max_steps: int,
        max_runtime_seconds: int,
        continuation: dict | None = None,
    ) -> str | None:
        elapsed = max(0, (datetime.now(UTC) - run.started_at).total_seconds())
        deadline = monotonic() + max_runtime_seconds - elapsed
        exchanges = load_exchanges(continuation["exchanges"]) if continuation else []
        first_step = continuation["step"] if continuation else 1
        for step in range(first_step, max_steps + 1):
            remaining = deadline - monotonic()
            if remaining <= 0:
                if step == 1:
                    call.status, call.error_type = "TIMED_OUT", "RUN_TIMEOUT"
                    call.completed_at = datetime.now(UTC)
                return "RUN_TIMEOUT"
            resuming_batch = continuation is not None and step == first_step
            if step > 1 and not resuming_batch:
                call = ModelCall(
                    run_id=run.id, provider=adapter.provider, model=request.model, status="RUNNING"
                )
                self.session.add(call)
                run.current_step = step
                run.model_calls_count += 1
                record_event(self.session, run, "MODEL_CALL_STARTED", {"step": step})
                await self.session.commit()
            if resuming_batch:
                result = load_result(continuation["result"])
            else:
                result, failure = await self.model_step(
                    run,
                    call,
                    adapter,
                    replace(
                        request,
                        timeout_seconds=min(request.timeout_seconds, remaining),
                        exchanges=exchanges,
                    ),
                )
                if failure:
                    return failure
            if result.finish_reason != "STOP":
                return "MODEL_RESPONSE_INCOMPLETE"
            if not result.tool_requests:
                if not result.text.strip():
                    return "MODEL_RESPONSE_INCOMPLETE"
                run.output = {"message": result.text}
                return None
            if step >= max_steps:
                return "STEP_LIMIT_EXCEEDED"
            if len(result.tool_requests) > MAX_CALLS_PER_TURN or (
                not resuming_batch
                and run.tool_calls_count + len(result.tool_requests) > MAX_TOOL_CALLS
            ):
                return "TOOL_CALL_LIMIT_EXCEEDED"
            transition_run(
                self.session,
                run,
                RunState.WAITING_FOR_TOOL,
                {"model_call_id": str(call.id), "requested_calls": len(result.tool_requests)},
            )
            await self.session.commit()
            results = []
            for index, tool_request in enumerate(result.tool_requests):
                if not isinstance(tool_request, dict):
                    tool_request = {"name": "<invalid>", "arguments": None}
                try:
                    recorded = await self.hub.execute(
                        run, call.id, index, tool_request, tools, deadline - monotonic()
                    )
                except ToolFailure as exc:
                    return exc.code
                if recorded.status == "WAITING_FOR_APPROVAL":
                    transition_run(
                        self.session,
                        run,
                        RunState.WAITING_FOR_APPROVAL,
                        {"tool_call_id": str(recorded.id)},
                    )
                    self.session.add(
                        RunCheckpoint(
                            run_id=run.id,
                            state_version=run.state_version,
                            last_event_sequence=run.state_version,
                            runtime_build_version=run.runtime_build_version,
                            runtime_state={
                                "step": step,
                                "model_call_id": str(call.id),
                                "result": save_result(result),
                                "exchanges": save_exchanges(exchanges),
                            },
                        )
                    )
                    await self.session.commit()
                    return None
                if recorded.error:
                    return recorded.error["code"]
                results.append(
                    {
                        "name": recorded.requested_name,
                        "id": tool_request.get("id"),
                        "result": recorded.result,
                    }
                )
            exchanges.append(ToolExchange(response=result, results=results))
            transition_run(self.session, run, RunState.RUNNING)
            await self.session.commit()
        return "STEP_LIMIT_EXCEEDED"
