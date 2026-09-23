from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge.tools.models import AgentTool, Tool, ToolCall


class ToolRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def tool(self, organization_id: UUID, tool_id: UUID, *, lock: bool = False):
        query = select(Tool).where(Tool.organization_id == organization_id, Tool.id == tool_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(query)

    async def by_name(self, organization_id: UUID, name: str, version: str):
        return await self.session.scalar(
            select(Tool).where(
                Tool.organization_id == organization_id,
                Tool.name == name,
                Tool.version == version,
            )
        )

    async def tools(self, organization_id: UUID, limit: int, offset: int):
        return list(
            await self.session.scalars(
                select(Tool)
                .where(Tool.organization_id == organization_id)
                .order_by(Tool.created_at, Tool.id)
                .limit(limit)
                .offset(offset)
            )
        )

    async def bindings(self, version_id: UUID):
        return list(
            await self.session.scalars(
                select(AgentTool.tool_id).where(AgentTool.agent_version_id == version_id)
            )
        )

    async def calls(self, run_id: UUID, limit: int, offset: int):
        return list(
            await self.session.scalars(
                select(ToolCall)
                .where(ToolCall.run_id == run_id)
                .order_by(ToolCall.created_at, ToolCall.id)
                .limit(limit)
                .offset(offset)
            )
        )

    async def call(self, model_call_id: UUID, call_index: int):
        return await self.session.scalar(
            select(ToolCall).where(
                ToolCall.model_call_id == model_call_id,
                ToolCall.call_index == call_index,
            )
        )
