from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from forge.api.registry import Limit, Scope, require_development_registry
from forge.db.session import get_session
from forge.model_router.base import ModelAdapter
from forge.model_router.fake import FakeAdapter
from forge.model_router.gemini import GeminiAdapter
from forge.runtime.schemas import EventRead, ModelCallRead, RunCreate, RunRead
from forge.runtime.service import RunService


def get_adapter(request: Request) -> ModelAdapter:
    settings = request.app.state.settings
    if settings.model_backend == "fake":
        return FakeAdapter()
    key = settings.gemini_api_key.get_secret_value().strip() if settings.gemini_api_key else None
    return GeminiAdapter(key)


def get_run_service(session: Annotated[AsyncSession, Depends(get_session)]) -> RunService:
    return RunService(session)


router = APIRouter(tags=["runs"], dependencies=[Depends(require_development_registry)])
Service = Annotated[RunService, Depends(get_run_service)]
Adapter = Annotated[ModelAdapter, Depends(get_adapter)]
Key = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$"),
]


@router.post("/runs", response_model=RunRead, status_code=201)
async def create_run(
    payload: RunCreate,
    scope: Scope,
    key: Key,
    service: Service,
    adapter: Adapter,
    request: Request,
    response: Response,
):
    run, created = await service.execute(scope, payload, key, adapter, request.app.state.settings)
    response.status_code = 201 if created else 200
    return run


@router.get("/runs/{run_id}", response_model=RunRead)
async def get_run(run_id: UUID, scope: Scope, service: Service):
    return await service.get(scope, run_id)


@router.get("/runs/{run_id}/events", response_model=list[EventRead])
async def get_events(
    run_id: UUID,
    scope: Scope,
    service: Service,
    after: Annotated[int, Query(ge=-1)] = -1,
    limit: Limit = 50,
):
    return await service.events(scope, run_id, after, limit)


@router.get("/runs/{run_id}/model-calls", response_model=list[ModelCallRead])
async def get_model_calls(run_id: UUID, scope: Scope, service: Service):
    return await service.calls(scope, run_id)
