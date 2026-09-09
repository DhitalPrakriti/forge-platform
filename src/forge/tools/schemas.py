from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from forge.agents.schemas import Schema


class ToolRegister(Schema):
    name: Literal["lookup_customer", "lookup_transactions", "create_ticket", "issue_refund"]
    version: Literal["1.0.0"] = "1.0.0"


class ToolPatch(Schema):
    status: Literal["ACTIVE", "INACTIVE"]


class ToolRead(Schema):
    id: UUID
    organization_id: UUID
    name: str
    version: str
    description: str
    input_schema: dict
    output_schema: dict
    risk_level: str
    timeout_seconds: int
    retry_safe: bool
    idempotency_supported: bool
    handler_type: str
    status: str
    created_at: datetime


class ToolCallRead(Schema):
    id: UUID
    run_id: UUID
    model_call_id: UUID
    call_index: int
    tool_id: UUID | None
    requested_name: str
    status: str
    arguments: Any
    result: dict | None
    error: dict | None
    decision: str
    idempotency_key: str
    request_hash: str
    latency_ms: int | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
