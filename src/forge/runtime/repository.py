from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge.agents.models import Agent, AgentVersion
from forge.runtime.models import ModelCall, Run, RunEvent


class RunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_key(self, organization_id: UUID, key: str):
        return await self.session.scalar(
            select(Run).where(Run.organization_id == organization_id, Run.idempotency_key == key)
        )

    async def run(self, organization_id: UUID, run_id: UUID):
        return await self.session.scalar(
            select(Run).where(Run.organization_id == organization_id, Run.id == run_id)
        )

    async def version(self, organization_id: UUID, version_id: UUID):
        query = (
            select(AgentVersion, Agent.status)
            .join(Agent)
            .where(AgentVersion.id == version_id, Agent.organization_id == organization_id)
            .with_for_update(of=(Agent, AgentVersion))
        )
        return (await self.session.execute(query)).first()

    async def events(self, run_id: UUID, after: int, limit: int):
        return list(
            await self.session.scalars(
                select(RunEvent)
                .where(RunEvent.run_id == run_id, RunEvent.sequence_number > after)
                .order_by(RunEvent.sequence_number)
                .limit(limit)
            )
        )

    async def calls(self, run_id: UUID):
        return list(
            await self.session.scalars(
                select(ModelCall)
                .where(ModelCall.run_id == run_id)
                .order_by(ModelCall.created_at, ModelCall.id)
            )
        )
