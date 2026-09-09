import secrets
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from pydantic import Field
from sqlalchemy import select

from forge.agents.schemas import Schema
from forge.api.registry import Limit, Offset, Scope, require_development_registry
from forge.api.runs import Adapter
from forge.api.tools import Session
from forge.approvals.models import Approval, Policy
from forge.approvals.policy import register_policy
from forge.approvals.service import ApprovalService
from forge.core.errors import DomainError
from forge.runtime.schemas import RunRead
from forge.tools.registry import ToolRegistry

router = APIRouter(
    tags=["policies and approvals"], dependencies=[Depends(require_development_registry)]
)


class PolicyRead(Schema):
    id: UUID
    organization_id: UUID
    name: str
    version: str
    rules: dict


class ApprovalRead(Schema):
    id: UUID
    organization_id: UUID
    run_id: UUID
    tool_call_id: UUID
    policy_id: UUID
    status: str
    summary: str
    requested_payload: dict
    request_hash: str
    expires_at: datetime
    requested_at: datetime
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    decision_reason: str | None


class DecisionInput(Schema):
    reason: str = Field(min_length=1, max_length=2000)


def reviewer(request: Request, authorization: Annotated[str | None, Header()] = None) -> UUID:
    settings = request.app.state.settings
    token = settings.approval_reviewer_token
    if token is None or settings.approval_reviewer_id is None:
        raise DomainError(
            "REVIEWER_NOT_CONFIGURED", "Configure a local reviewer credential server-side.", 503
        )
    if not authorization or not secrets.compare_digest(
        authorization, "Bearer " + token.get_secret_value()
    ):
        raise DomainError("REVIEWER_UNAUTHORIZED", "A valid reviewer credential is required.", 401)
    return settings.approval_reviewer_id


Reviewer = Annotated[UUID, Depends(reviewer)]


@router.post("/policies", response_model=PolicyRead)
async def create_policy(scope: Scope, session: Session):
    await ToolRegistry(session).organization(scope)
    return await register_policy(session, scope)


@router.get("/policies", response_model=list[PolicyRead])
async def policies(scope: Scope, session: Session, limit: Limit = 50, offset: Offset = 0):
    return list(
        await session.scalars(
            select(Policy)
            .where(Policy.organization_id == scope)
            .order_by(Policy.created_at, Policy.id)
            .limit(limit)
            .offset(offset)
        )
    )


@router.get("/approvals", response_model=list[ApprovalRead])
async def approvals(
    scope: Scope,
    session: Session,
    run_id: UUID | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    query = select(Approval).where(Approval.organization_id == scope)
    if run_id:
        query = query.where(Approval.run_id == run_id)
    return list(
        await session.scalars(
            query.order_by(Approval.requested_at.desc(), Approval.id).limit(limit).offset(offset)
        )
    )


@router.get("/approvals/{approval_id}", response_model=ApprovalRead)
async def approval(approval_id: UUID, scope: Scope, session: Session):
    return await ApprovalService(session).get(scope, approval_id)


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalRead)
async def approve(
    approval_id: UUID, payload: DecisionInput, scope: Scope, session: Session, identity: Reviewer
):
    return await ApprovalService(session).decide(
        scope, approval_id, "APPROVED", payload.reason, identity
    )


@router.post("/approvals/{approval_id}/deny", response_model=ApprovalRead)
async def deny(
    approval_id: UUID, payload: DecisionInput, scope: Scope, session: Session, identity: Reviewer
):
    return await ApprovalService(session).decide(
        scope, approval_id, "DENIED", payload.reason, identity
    )


@router.post("/runs/{run_id}/resume", response_model=RunRead)
async def resume(
    run_id: UUID, scope: Scope, session: Session, adapter: Adapter, identity: Reviewer
):
    return await ApprovalService(session).resume(scope, run_id, adapter)
