from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge.agents.models import Agent, AgentVersion, Organization


class RegistryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def organization(self, organization_id: UUID) -> Organization | None:
        return await self.session.get(Organization, organization_id)

    async def agent(self, organization_id: UUID, agent_id: UUID, *, lock: bool = False):
        query = select(Agent).where(Agent.id == agent_id, Agent.organization_id == organization_id)
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def agents(self, organization_id: UUID, limit: int, offset: int):
        query = (
            select(Agent)
            .where(Agent.organization_id == organization_id)
            .order_by(Agent.created_at, Agent.id)
            .limit(limit)
            .offset(offset)
        )
        return list(await self.session.scalars(query))

    async def version(self, organization_id: UUID, version_id: UUID, *, lock: bool = False):
        query = (
            select(AgentVersion)
            .join(Agent)
            .where(Agent.organization_id == organization_id, AgentVersion.id == version_id)
        )
        if lock:
            query = query.with_for_update(of=AgentVersion)
        return await self.session.scalar(query)

    async def versions(self, agent_id: UUID, limit: int, offset: int):
        # Caller must resolve the organization-scoped parent first.
        query = (
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.created_at, AgentVersion.id)
            .limit(limit)
            .offset(offset)
        )
        return list(await self.session.scalars(query))

    def add(self, entity):
        self.session.add(entity)
