from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from forge.agents.schemas import (
    AgentCreate,
    AgentPatch,
    AgentRead,
    OrganizationCreate,
    OrganizationRead,
    VersionCreate,
    VersionRead,
)
from forge.agents.service import RegistryService
from forge.core.errors import DomainError
from forge.db.session import get_session


def require_development_registry(request: Request) -> None:
    if request.app.state.settings.environment == "production":
        raise DomainError(
            "REGISTRY_AUTH_REQUIRED",
            "Registry requires authenticated membership in production.",
            503,
        )


def organization_scope(
    organization_id: Annotated[UUID, Header(alias="X-Organization-ID")],
) -> UUID:
    # Development context only: this header is NOT an authentication credential.
    return organization_id


def registry_service(session: Annotated[AsyncSession, Depends(get_session)]) -> RegistryService:
    return RegistryService(session)


router = APIRouter(tags=["registry"], dependencies=[Depends(require_development_registry)])
Service = Annotated[RegistryService, Depends(registry_service)]
Scope = Annotated[UUID, Depends(organization_scope)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.post("/organizations", response_model=OrganizationRead, status_code=201)
async def create_organization(payload: OrganizationCreate, service: Service):
    return await service.create_organization(payload)


@router.get("/organizations/current", response_model=OrganizationRead)
async def current_organization(scope: Scope, service: Service):
    return await service.organization(scope)


@router.post("/agents", response_model=AgentRead, status_code=201)
async def create_agent(payload: AgentCreate, scope: Scope, service: Service):
    return await service.create_agent(scope, payload)


@router.get("/agents", response_model=list[AgentRead])
async def list_agents(scope: Scope, service: Service, limit: Limit = 50, offset: Offset = 0):
    return await service.agents(scope, limit, offset)


@router.get("/agents/{agent_id}", response_model=AgentRead)
async def get_agent(agent_id: UUID, scope: Scope, service: Service):
    return await service.agent(scope, agent_id)


@router.patch("/agents/{agent_id}", response_model=AgentRead)
async def patch_agent(agent_id: UUID, payload: AgentPatch, scope: Scope, service: Service):
    return await service.patch_agent(scope, agent_id, payload)


@router.post("/agents/{agent_id}/versions", response_model=VersionRead, status_code=201)
async def create_version(agent_id: UUID, payload: VersionCreate, scope: Scope, service: Service):
    return await service.create_version(scope, agent_id, payload)


@router.get("/agents/{agent_id}/versions", response_model=list[VersionRead])
async def list_versions(
    agent_id: UUID, scope: Scope, service: Service, limit: Limit = 50, offset: Offset = 0
):
    return await service.versions(scope, agent_id, limit, offset)


@router.get("/agents/{agent_id}/versions/{version_id}", response_model=VersionRead)
async def get_version(agent_id: UUID, version_id: UUID, scope: Scope, service: Service):
    return await service.nested_version(scope, agent_id, version_id)


@router.patch("/agents/{agent_id}/versions/{version_id}")
async def reject_version_edit(agent_id: UUID, version_id: UUID, scope: Scope, service: Service):
    await service.nested_version(scope, agent_id, version_id)
    raise DomainError("VERSION_IMMUTABLE", "Create a new version to change configuration.", 409)


@router.post("/agent-versions/{version_id}/archive", response_model=VersionRead)
async def archive_version(version_id: UUID, scope: Scope, service: Service):
    return await service.archive(scope, version_id)


@router.post("/agent-versions/{version_id}/stage", response_model=VersionRead)
async def stage_version(version_id: UUID, scope: Scope, service: Service):
    return await service.stage(scope, version_id)
