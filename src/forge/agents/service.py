from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from forge.agents.lifecycle import Lifecycle, validate_transition
from forge.agents.models import Agent, AgentVersion, Organization
from forge.agents.repository import RegistryRepository
from forge.agents.schemas import AgentCreate, AgentPatch, OrganizationCreate, VersionCreate
from forge.core.errors import DomainError
from forge.tools.models import AgentTool
from forge.tools.registry import ToolRegistry


class RegistryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = RegistryRepository(session)

    async def commit(self, conflict_code: str):
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise DomainError(conflict_code, "This identifier already exists.", 409) from exc
            raise

    async def create_organization(self, payload: OrganizationCreate):
        entity = Organization(**payload.model_dump())
        self.repository.add(entity)
        await self.commit("ORGANIZATION_SLUG_EXISTS")
        return entity

    async def organization(self, organization_id: UUID):
        entity = await self.repository.organization(organization_id)
        if entity is None:
            raise DomainError("ORGANIZATION_NOT_FOUND", "Organization not found.", 404)
        return entity

    async def create_agent(self, organization_id: UUID, payload: AgentCreate):
        await self.organization(organization_id)
        entity = Agent(organization_id=organization_id, **payload.model_dump())
        self.repository.add(entity)
        await self.commit("AGENT_SLUG_EXISTS")
        return entity

    async def agent(self, organization_id: UUID, agent_id: UUID, *, lock: bool = False):
        entity = await self.repository.agent(organization_id, agent_id, lock=lock)
        if entity is None:
            raise DomainError("AGENT_NOT_FOUND", "Agent not found.", 404)
        return entity

    async def agents(self, organization_id: UUID, limit: int, offset: int):
        await self.organization(organization_id)
        return await self.repository.agents(organization_id, limit, offset)

    async def patch_agent(self, organization_id: UUID, agent_id: UUID, payload: AgentPatch):
        entity = await self.agent(organization_id, agent_id, lock=True)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(entity, key, value)
        await self.commit("AGENT_SLUG_EXISTS")
        await self.session.refresh(entity)
        return entity

    async def create_version(self, organization_id: UUID, agent_id: UUID, payload: VersionCreate):
        agent = await self.agent(organization_id, agent_id, lock=True)
        if agent.status != "ACTIVE":
            raise DomainError("AGENT_INACTIVE", "Cannot version an inactive agent.", 409)
        tools = await ToolRegistry(self.session).resolve(organization_id, payload.tool_version_ids)
        config = payload.model_dump(mode="json")
        config["evaluation_suite_version_id"] = payload.evaluation_suite_version_id
        entity = AgentVersion(agent_id=agent_id, **config)
        self.repository.add(entity)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise DomainError("VERSION_EXISTS", "This identifier already exists.", 409) from exc
            raise
        for tool in tools:
            self.session.add(AgentTool(agent_version_id=entity.id, tool_id=tool.id))
        await self.commit("VERSION_EXISTS")
        return entity

    async def version(self, organization_id: UUID, version_id: UUID, *, lock: bool = False):
        entity = await self.repository.version(organization_id, version_id, lock=lock)
        if entity is None:
            raise DomainError("VERSION_NOT_FOUND", "Version not found.", 404)
        return entity

    async def nested_version(self, organization_id: UUID, agent_id: UUID, version_id: UUID):
        await self.agent(organization_id, agent_id)
        entity = await self.version(organization_id, version_id)
        if entity.agent_id != agent_id:
            raise DomainError("VERSION_NOT_FOUND", "Version not found.", 404)
        return entity

    async def versions(self, organization_id: UUID, agent_id: UUID, limit: int, offset: int):
        await self.agent(organization_id, agent_id)
        return await self.repository.versions(agent_id, limit, offset)

    async def archive(self, organization_id: UUID, version_id: UUID):
        entity = await self.version(organization_id, version_id, lock=True)
        validate_transition(Lifecycle(entity.lifecycle_status), Lifecycle.ARCHIVED)
        entity.lifecycle_status = Lifecycle.ARCHIVED.value
        await self.commit("VERSION_EXISTS")
        return entity

    async def stage(self, organization_id: UUID, version_id: UUID):
        entity = await self.version(organization_id, version_id, lock=True)
        validate_transition(Lifecycle(entity.lifecycle_status), Lifecycle.STAGING)
        if entity.evaluation_suite_version_id is None:
            raise DomainError(
                "EVALUATION_SUITE_REQUIRED", "Staging requires an evaluation suite.", 409
            )
        # Do not claim that UUIDs exist before their owning registries are implemented.
        raise DomainError(
            "STAGING_DEPENDENCIES_UNAVAILABLE",
            "Staging validation requires the model, tool, policy, and evaluation registries.",
            409,
        )
