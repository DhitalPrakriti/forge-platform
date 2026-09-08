from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from forge.api.registry import Limit, Offset, Scope, require_development_registry
from forge.db.session import get_session
from forge.runtime.service import RunService
from forge.tools.registry import ToolRegistry
from forge.tools.repository import ToolRepository
from forge.tools.schemas import ToolCallRead, ToolPatch, ToolRead, ToolRegister

router = APIRouter(tags=["tools"], dependencies=[Depends(require_development_registry)])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.post("/tools", response_model=ToolRead, status_code=201)
async def register_tool(payload: ToolRegister, scope: Scope, session: Session, response: Response):
    tool, created = await ToolRegistry(session).register(scope, payload)
    response.status_code = 201 if created else 200
    return tool


@router.get("/tools", response_model=list[ToolRead])
async def list_tools(scope: Scope, session: Session, limit: Limit = 50, offset: Offset = 0):
    return await ToolRegistry(session).tools(scope, limit, offset)


@router.get("/tools/{tool_id}", response_model=ToolRead)
async def get_tool(tool_id: UUID, scope: Scope, session: Session):
    return await ToolRegistry(session).get(scope, tool_id)


@router.patch("/tools/{tool_id}", response_model=ToolRead)
async def patch_tool(tool_id: UUID, payload: ToolPatch, scope: Scope, session: Session):
    return await ToolRegistry(session).patch(scope, tool_id, payload)


@router.get("/runs/{run_id}/tool-calls", response_model=list[ToolCallRead])
async def tool_calls(
    run_id: UUID, scope: Scope, session: Session, limit: Limit = 50, offset: Offset = 0
):
    await RunService(session).get(scope, run_id)
    return await ToolRepository(session).calls(run_id, limit, offset)
