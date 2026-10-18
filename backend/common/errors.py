import logging
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class Code(StrEnum):
    BAD_REQUEST = "BAD_REQUEST"
    BAD_ATTRIBUTES = "BAD_ATTRIBUTES"
    BAD_TIMING = "BAD_TIMING"
    FUTURE_TIMESTAMP = "FUTURE_TIMESTAMP"
    HASH_MISMATCH = "HASH_MISMATCH"
    CHAIN_BROKEN = "CHAIN_BROKEN"
    UNAUTHORIZED = "UNAUTHORIZED"
    RATE_LIMITED = "RATE_LIMITED"
    TOO_LARGE = "TOO_LARGE"
    NOT_FOUND = "NOT_FOUND"
    BAD_INTERVENTION = "BAD_INTERVENTION"
    INTERNAL = "INTERNAL"
    UNAVAILABLE = "UNAVAILABLE"


class ApiError(Exception):
    def __init__(
        self, code: Code, message: str, status: int = 400, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code, self.status, self.details = code, status, details or {}


def envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def install_errors(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        code = Code.NOT_FOUND if error.status_code == 404 else Code.BAD_REQUEST
        return JSONResponse(envelope(code, str(error.detail)), error.status_code)

    @app.exception_handler(ApiError)
    async def api_error(request: Request, error: ApiError) -> JSONResponse:
        headers = {"Retry-After": "1"} if error.status == 429 else None
        return JSONResponse(
            envelope(error.code, str(error), error.details), error.status, headers=headers
        )

    @app.exception_handler(RequestValidationError)
    async def validation(request: Request, error: RequestValidationError) -> JSONResponse:
        issues = [{"loc": list(item["loc"]), "type": item["type"]} for item in error.errors()]
        return JSONResponse(envelope(Code.BAD_REQUEST, "Invalid request", {"issues": issues}), 400)

    @app.exception_handler(Exception)
    async def internal(request: Request, error: Exception) -> JSONResponse:
        logger.exception("request_failed path=%s", request.url.path, exc_info=error)
        return JSONResponse(envelope(Code.INTERNAL, "Internal server error"), 500)
