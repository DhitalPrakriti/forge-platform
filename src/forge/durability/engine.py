"""Recoverable execution cursor. Reuses the model adapter and the existing Tool Hub."""

import random
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from importlib.metadata import version as package_version
from uuid import UUID

from sqlalchemy import select

from forge.approvals.models import Approval
from forge.approvals.policy import resolve_policy
from forge.core.errors import DomainError
from forge.durability.models import RunControl
from forge.durability.store import BUILD, SCHEMA, checkpoint, latest
from forge.model_router.base import ModelRequest, ToolExchange
from forge.runtime.checkpoints import load_exchanges, load_result, save_exchanges, save_result
from forge.runtime.engine import RuntimeEngine
from forge.runtime.events import record_event, transition_run
from forge.runtime.models import ModelCall
from forge.runtime.repository import RunRepository
from forge.runtime.state import RunState
from forge.tools.builtins import ToolFailure
from forge.tools.hub import MAX_CALLS_PER_TURN, MAX_TOOL_CALLS, ToolHub
from forge.tools.models import ToolCall
from forge.tools.registry import ToolRegistry
from forge.tools.repository import ToolRepository

TRANSIENT = {"MODEL_TIMEOUT", "MODEL_PROVIDER_UNAVAILABLE", "MODEL_OUTCOME_UNKNOWN"}


class DurableEngine:
    def __init__(self, session, adapter):
        self.session, self.adapter = session, adapter

    async def save(self, run, state, **kwargs):
        await checkpoint(self.session, run, state, **kwargs)
        await self.session.commit()

    async def finish(self, run, code=None, target=None):
        target = target or (
            RunState.CANCELLED
            if code == "RUN_CANCELLED"
            else RunState.COMPLETED
            if code is None
            else RunState.TIMED_OUT
            if code in {"RUN_TIMEOUT", "MODEL_TIMEOUT", "TOOL_TIMEOUT"}
            else RunState.FAILED
        )
        run.error_code, run.completed_at = code, datetime.now(UTC)
        pending = await self.session.scalars(
            select(ToolCall).where(
                ToolCall.run_id == run.id, ToolCall.status == "WAITING_FOR_APPROVAL"
            )
        )
        for call in pending:
            call.status, call.error, call.completed_at = "DENIED", {"code": code}, run.completed_at
            record_event(
                self.session,
                run,
                "TOOL_CALL_FINISHED",
                {"tool_call_id": str(call.id), "status": call.status, "error_code": code},
            )
        transition_run(self.session, run, target, {"error_code": code})
        await self.save(run, {"phase": "TERMINAL", "error_code": code}, terminal=True)

    def remaining(self, run):
        return (
            run.execution_config["max_runtime_seconds"]
            - (datetime.now(UTC) - run.started_at).total_seconds()
        )

    async def stopped(self, run):
        cancelled = await self.session.scalar(
            select(RunControl.cancel_requested_at).where(RunControl.run_id == run.id)
        )
        if cancelled:
            await self.finish(run, "RUN_CANCELLED", RunState.CANCELLED)
            return True
        if self.remaining(run) <= 0:
            if run.status == "WAITING_FOR_APPROVAL":
                approvals = await self.session.scalars(
                    select(Approval).where(Approval.run_id == run.id, Approval.status == "PENDING")
                )
                for approval in approvals:
                    approval.status = "EXPIRED"
                await self.finish(run, "APPROVAL_EXPIRED", RunState.CANCELLED)
            else:
                await self.finish(run, "RUN_TIMEOUT")
            return True
        return False

    async def retry(self, run, state, code):
        if code not in TRANSIENT or state["attempt"] >= run.execution_config["model_max_attempts"]:
            await self.finish(run, code)
            return
        delay = run.execution_config["retry_base_seconds"] * 2 ** (state["attempt"] - 1)
        delay += random.uniform(0, delay / 4)
        due = min(
            datetime.now(UTC) + timedelta(seconds=delay),
            run.started_at + timedelta(seconds=run.execution_config["max_runtime_seconds"]),
        )
        state = {**state, "model_call_id": None}
        transition_run(
            self.session,
            run,
            RunState.RETRYING,
            {"error_code": code, "attempt": state["attempt"], "next_attempt_at": due.isoformat()},
        )
        await self.save(run, state, due=due)

    async def execute(self, run):
        if await self.stopped(run):
            return
        saved = await latest(self.session, run.id)
        if (
            saved is None
            or saved.runtime_build_version != BUILD
            or run.runtime_build_version != BUILD
            or saved.checkpoint_schema_version != SCHEMA
        ):
            await self.finish(run, "CHECKPOINT_INCOMPATIBLE")
            return
        state = dict(saved.runtime_state)
        config = run.execution_config
        if config["provider"] != self.adapter.provider or (
            self.adapter.provider == "google"
            and config["provider_sdk_version"] != package_version("google-genai")
        ):
            await self.finish(run, "CHECKPOINT_INCOMPATIBLE")
            return
        row = await RunRepository(self.session).version(run.organization_id, run.agent_version_id)
        if row is None:
            await self.finish(run, "VERSION_NOT_FOUND")
            return
        version, _ = row
        try:
            self.adapter.validate(version.primary_model)
            tools = await ToolRegistry(self.session).resolve(
                run.organization_id, version.tool_version_ids
            )
            await resolve_policy(
                self.session,
                run.organization_id,
                version.policy_version_ids,
                required=any(t.name == "issue_refund" for t in tools),
            )
            if set(await ToolRepository(self.session).bindings(version.id)) != {
                t.id for t in tools
            }:
                raise DomainError("TOOL_BINDING_INVALID", "Pinned permissions differ.", 409)
            if (
                state.get("phase") not in {"MODEL", "TOOLS"}
                or type(state.get("step")) is not int
                or not 1 <= state["step"] <= version.runtime_config["max_steps"] + 1
                or type(state.get("attempt")) is not int
                or not 0 <= state["attempt"] <= config["model_max_attempts"]
                or not isinstance(state.get("exchanges"), list)
            ):
                raise ValueError("Invalid continuation cursor")
            if state.get("model_call_id"):
                recorded_call = await self.session.get(ModelCall, UUID(state["model_call_id"]))
                if recorded_call is None or recorded_call.run_id != run.id:
                    raise ValueError("Invalid model call binding")
            if state["phase"] == "TOOLS":
                restored = load_result(state["result"])
                if (
                    not state.get("model_call_id")
                    or not isinstance(restored.tool_requests, list)
                    or not 1 <= len(restored.tool_requests) <= MAX_CALLS_PER_TURN
                    or type(state.get("index")) is not int
                    or not 0 <= state["index"] <= len(restored.tool_requests)
                    or not isinstance(state.get("results"), list)
                    or len(state["results"]) != state["index"]
                ):
                    raise ValueError("Invalid tool cursor")
            exchanges = load_exchanges(state["exchanges"])
            if state["phase"] == "TOOLS":
                load_result(state["result"])
        except DomainError as exc:
            await self.finish(run, exc.code)
            return
        except (ValueError, TypeError, KeyError):
            await self.finish(run, "CHECKPOINT_INCOMPATIBLE")
            return
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
        if run.status == "WAITING_FOR_APPROVAL":
            approval = await self.session.scalar(
                select(Approval)
                .where(Approval.run_id == run.id)
                .order_by(Approval.requested_at.desc())
                .limit(1)
            )
            if approval is None:
                await self.finish(run, "APPROVAL_NOT_FOUND")
                return
            if approval.expires_at <= datetime.now(UTC):
                if approval.status == "PENDING":
                    approval.status = "EXPIRED"
                await self.finish(run, "APPROVAL_EXPIRED", RunState.CANCELLED)
                return
            if approval.status != "APPROVED":
                # Leave a durable expiry wake-up; no busy approval polling in the worker.
                await self.save(run, state, due=approval.expires_at)
                return
            transition_run(self.session, run, RunState.RUNNING)
            transition_run(self.session, run, RunState.WAITING_FOR_TOOL)
            await self.save(run, state)
        elif run.status in {"QUEUED", "RETRYING"}:
            transition_run(self.session, run, RunState.RUNNING)
            await self.save(run, state)
        while not await self.stopped(run):
            if state["phase"] == "MODEL":
                if state["step"] > version.runtime_config["max_steps"]:
                    await self.finish(run, "STEP_LIMIT_EXCEEDED")
                    return
                if state["model_call_id"]:
                    # A killed worker may have contacted the provider. Record the unknown
                    # attempt and apply the same durable attempt cap/backoff as a timeout.
                    call = await self.session.get(ModelCall, UUID(state["model_call_id"]))
                    call.status, call.error_type, call.completed_at = (
                        "FAILED",
                        "MODEL_OUTCOME_UNKNOWN",
                        datetime.now(UTC),
                    )
                    await self.retry(run, state, "MODEL_OUTCOME_UNKNOWN")
                    return
                call = ModelCall(
                    run_id=run.id,
                    provider=self.adapter.provider,
                    model=request.model,
                    status="RUNNING",
                )
                self.session.add(call)
                run.current_step = state["step"]
                run.model_calls_count += 1
                record_event(
                    self.session,
                    run,
                    "MODEL_CALL_STARTED",
                    {"step": state["step"], "attempt": state["attempt"] + 1},
                )
                await self.session.flush()
                state = {**state, "attempt": state["attempt"] + 1, "model_call_id": str(call.id)}
                await self.save(run, state)
                result, failure = await RuntimeEngine(self.session).model_step(
                    run,
                    call,
                    self.adapter,
                    replace(
                        request,
                        timeout_seconds=min(request.timeout_seconds, self.remaining(run)),
                        exchanges=exchanges,
                    ),
                )
                if await self.stopped(run):
                    return
                if failure:
                    await self.retry(run, state, failure)
                    return
                if result.finish_reason != "STOP":
                    await self.finish(run, "MODEL_RESPONSE_INCOMPLETE")
                    return
                if not result.tool_requests:
                    if not result.text.strip():
                        await self.finish(run, "MODEL_RESPONSE_INCOMPLETE")
                        return
                    run.output = {"message": result.text}
                    await self.finish(run)
                    return
                if state["step"] >= version.runtime_config["max_steps"]:
                    await self.finish(run, "STEP_LIMIT_EXCEEDED")
                    return
                if (
                    len(result.tool_requests) > MAX_CALLS_PER_TURN
                    or run.tool_calls_count + len(result.tool_requests) > MAX_TOOL_CALLS
                ):
                    await self.finish(run, "TOOL_CALL_LIMIT_EXCEEDED")
                    return
                state = {
                    **state,
                    "phase": "TOOLS",
                    "result": save_result(result),
                    "index": 0,
                    "results": [],
                }
                transition_run(self.session, run, RunState.WAITING_FOR_TOOL)
                await self.save(run, state)
            elif state["phase"] == "TOOLS":
                result = load_result(state["result"])
                if state["index"] >= len(result.tool_requests):
                    exchanges.append(ToolExchange(response=result, results=state["results"]))
                    state = {
                        "phase": "MODEL",
                        "step": state["step"] + 1,
                        "attempt": 0,
                        "model_call_id": None,
                        "exchanges": save_exchanges(exchanges),
                    }
                    transition_run(self.session, run, RunState.RUNNING)
                    await self.save(run, state)
                    continue
                tool_request = result.tool_requests[state["index"]]
                if not isinstance(tool_request, dict):
                    tool_request = {"name": "<invalid>", "arguments": None}
                next_state = None

                async def completed(call, state=state, tool_request=tool_request):
                    nonlocal next_state
                    if call.error:
                        return
                    next_state = {
                        **state,
                        "index": state["index"] + 1,
                        "results": [
                            *state["results"],
                            {
                                "name": call.requested_name,
                                "id": tool_request.get("id"),
                                "result": call.result,
                            },
                        ],
                    }
                    await checkpoint(self.session, run, next_state)

                try:
                    call = await ToolHub(self.session).execute(
                        run,
                        UUID(state["model_call_id"]),
                        state["index"],
                        tool_request,
                        tools,
                        self.remaining(run),
                        recover_local=True,
                        on_complete=completed,
                    )
                except ToolFailure as exc:
                    await self.finish(run, exc.code)
                    return
                if call.status == "WAITING_FOR_APPROVAL":
                    approval = await self.session.scalar(
                        select(Approval).where(Approval.tool_call_id == call.id)
                    )
                    transition_run(
                        self.session,
                        run,
                        RunState.WAITING_FOR_APPROVAL,
                        {"approval_id": str(approval.id)},
                    )
                    await self.save(run, state, due=approval.expires_at)
                    return
                if call.error:
                    await self.finish(run, call.error["code"])
                    return
                if next_state is None:
                    # Older checkpoint, newer committed ledger: reuse without execution.
                    await completed(call)
                    await self.session.commit()
                state = next_state
            else:
                await self.finish(run, "CHECKPOINT_INCOMPATIBLE")
                return
