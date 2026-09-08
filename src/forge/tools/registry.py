from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from forge.agents.models import Organization
from forge.core.errors import DomainError
from forge.tools.builtins import DEFINITIONS
from forge.tools.models import Tool
from forge.tools.repository import ToolRepository
from forge.tools.schemas import ToolPatch, ToolRegister


class ToolRegistry:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = ToolRepository(session)

    async def organization(self, organization_id: UUID):
        if await self.session.get(Organization, organization_id) is None:
            raise DomainError("ORGANIZATION_NOT_FOUND", "Organization not found.", 404)

    async def get(self, organization_id: UUID, tool_id: UUID, *, lock: bool = False):
        tool = await self.repository.tool(organization_id, tool_id, lock=lock)
        if tool is None:
            raise DomainError("TOOL_NOT_FOUND", "Tool revision not found.", 404)
        return tool

    async def tools(self, organization_id: UUID, limit: int, offset: int):
        await self.organization(organization_id)
        return await self.repository.tools(organization_id, limit, offset)

    async def register(self, organization_id: UUID, payload: ToolRegister):
        await self.organization(organization_id)
        existing = await self.repository.by_name(organization_id, payload.name, payload.version)
        if existing:
            return existing, False
        tool = Tool(organization_id=organization_id, **DEFINITIONS[payload.name].metadata())
        self.session.add(tool)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if getattr(exc.orig, "sqlstate", None) != "23505":
                raise
            existing = await self.repository.by_name(organization_id, payload.name, payload.version)
            if existing is None:
                raise
            return existing, False
        return tool, True

    async def patch(self, organization_id: UUID, tool_id: UUID, payload: ToolPatch):
        tool = await self.get(organization_id, tool_id, lock=True)
        tool.status = payload.status
        await self.session.commit()
        return tool

    async def resolve(self, organization_id: UUID, ids: list) -> list[Tool]:
        tools, names = [], set()
        for value in ids:
            tool = await self.get(organization_id, UUID(str(value)))
            definition = DEFINITIONS.get(tool.name)
            if tool.status != "ACTIVE":
                raise DomainError("TOOL_INACTIVE", "A bound tool is inactive.", 409)
            if definition is None or any(
                getattr(tool, key) != val for key, val in definition.metadata().items()
            ):
                raise DomainError(
                    "TOOL_REVISION_UNAVAILABLE",
                    "The pinned tool implementation is unavailable.",
                    409,
                )
            if tool.name in names:
                raise DomainError(
                    "TOOL_NAME_AMBIGUOUS", "Bind only one revision of each tool name.", 409
                )
            names.add(tool.name)
            tools.append(tool)
        return tools
