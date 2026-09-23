from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


class DomainError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None) or f"tr_{uuid4().hex}"
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "trace_id": trace_id, "details": {}}},
        headers={"X-Trace-ID": trace_id},
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return error_response(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Validation input/context can contain credentials or sensitive user payloads.
        return error_response(request, 422, "VALIDATION_ERROR", "Request validation failed.")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        response = error_response(
            request, exc.status_code, f"HTTP_{exc.status_code}", "HTTP request failed."
        )
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        return error_response(request, 500, "INTERNAL_ERROR", "An unexpected error occurred.")
