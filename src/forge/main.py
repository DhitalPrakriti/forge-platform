import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request

from forge.api.health import router
from forge.api.registry import router as registry_router
from forge.core.config import Settings
from forge.core.errors import error_response, install_error_handlers
from forge.db.session import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = config
        app.state.database = Database(config)
        try:
            yield
        finally:
            await app.state.database.close()

    app = FastAPI(title="FORGE", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def trace_request(request: Request, call_next):
        request.state.trace_id = f"tr_{uuid4().hex}"
        try:
            response = await call_next(request)
        except Exception:
            # Do not let server traceback logging expose exception payloads or credentials.
            logging.getLogger("forge.errors").error(
                "INTERNAL_ERROR trace_id=%s", request.state.trace_id
            )
            response = error_response(
                request, 500, "INTERNAL_ERROR", "An unexpected error occurred."
            )
        response.headers["X-Trace-ID"] = request.state.trace_id
        return response

    install_error_handlers(app)
    app.include_router(router, prefix="/api/v1")
    app.include_router(registry_router, prefix="/api/v1")
    return app
