"""HTTP error helpers — responses are {"detail": "...", "code": "..."}."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(
        self,
        detail: str,
        *,
        code: str = "app_error",
        status_code: int = 400,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status_code = status_code
        self.headers = headers


def error_body(detail: str, code: str) -> dict[str, str]:
    return {"detail": detail, "code": code}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.detail, exc.code),
            headers=exc.headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        code = "http_error"
        if isinstance(exc.detail, dict):
            detail = str(exc.detail.get("detail", exc.detail))
            code = str(exc.detail.get("code", code))
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(detail, code),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation failed",
                "code": "validation_error",
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
        # Avoid leaking internals; log elsewhere via middleware/logger.
        return JSONResponse(
            status_code=500,
            content=error_body("Internal server error", "internal_error"),
        )
