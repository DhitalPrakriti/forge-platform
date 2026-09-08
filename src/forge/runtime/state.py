from enum import StrEnum

from forge.core.errors import DomainError


class RunState(StrEnum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_FOR_TOOL = "WAITING_FOR_TOOL"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


TERMINAL = {RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED, RunState.TIMED_OUT}
TRANSITIONS = {
    RunState.CREATED: {RunState.QUEUED, RunState.RUNNING},  # Direct path for Phase 3.
    RunState.QUEUED: {RunState.RUNNING},
    RunState.RUNNING: {
        RunState.WAITING_FOR_TOOL,
        RunState.WAITING_FOR_APPROVAL,
        RunState.RETRYING,
        RunState.COMPLETED,
    },
    RunState.WAITING_FOR_TOOL: {RunState.RUNNING, RunState.RETRYING},
    RunState.WAITING_FOR_APPROVAL: {RunState.RUNNING},
    RunState.RETRYING: {RunState.RUNNING},
}


def validate_transition(current: RunState, target: RunState) -> None:
    allowed = TRANSITIONS.get(current, set()) | {
        RunState.FAILED,
        RunState.CANCELLED,
        RunState.TIMED_OUT,
    }
    if current in TERMINAL or target not in allowed:
        raise DomainError("INVALID_RUN_STATE", f"Cannot move from {current} to {target}.", 409)
