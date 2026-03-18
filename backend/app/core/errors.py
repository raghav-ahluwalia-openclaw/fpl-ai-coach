from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:  # noqa: ARG001
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "ok": False,
                "error": {
                    "type": "http_error",
                    "message": detail,
                    "status": exc.status_code,
                    "timestamp": _ts(),
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:  # noqa: ARG001
        return JSONResponse(
            status_code=422,
            content={
                "ok": False,
                "error": {
                    "type": "validation_error",
                    "message": "Request validation failed",
                    "status": 422,
                    "details": exc.errors(),
                    "timestamp": _ts(),
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "type": "internal_error",
                    "message": "Internal server error",
                    "status": 500,
                    "timestamp": _ts(),
                },
            },
        )
