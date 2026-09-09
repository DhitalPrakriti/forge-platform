from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import StringConstraints, field_serializer

from forge.agents.schemas import Schema
from forge.runtime.state import RunState


class RunInput(Schema):
    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)
    ]


class RunCreate(Schema):
    agent_version_id: UUID
    input: RunInput


class RunRead(Schema):
    retry_of_run_id: UUID | None = None
    id: UUID
    organization_id: UUID
    agent_id: UUID
    agent_version_id: UUID
    status: RunState
    state_version: int
    input: dict
    output: dict | None
    error_code: str | None
    current_step: int
    model_calls_count: int
    tool_calls_count: int
    total_cost: Decimal | None
    runtime_build_version: str
    execution_config: dict
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("total_cost")
    def serialize_cost(self, value: Decimal | None):
        return format(value, ".8f") if value is not None else None


class EventRead(Schema):
    id: UUID
    run_id: UUID
    sequence_number: int
    event_type: str
    payload: dict
    created_at: datetime


class ModelCallRead(Schema):
    id: UUID
    run_id: UUID
    provider: str
    model: str
    actual_model: str | None
    status: str
    input_tokens: int | None
    output_tokens: int | None
    usage: dict | None
    latency_ms: int | None
    estimated_cost: Decimal | None
    error_type: str | None
    created_at: datetime
    completed_at: datetime | None

    @field_serializer("estimated_cost")
    def serialize_cost(self, value: Decimal | None):
        return format(value, ".8f") if value is not None else None
