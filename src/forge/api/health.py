from fastapi import APIRouter, Request

from forge.health.service import check_database

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, str]:
    await check_database(
        request.app.state.database.engine,
        request.app.state.settings.database_timeout_seconds,
    )
    return {"status": "ready"}
