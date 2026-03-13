"""
MCPilot — Global Error Handler
Catches unhandled exceptions and returns a consistent JSON envelope.
Prevents stack traces leaking to clients in production.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.logging import get_logger

logger = get_logger(__name__)


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Handles all HTTPExceptions with consistent envelope."""
    logger.warning(
        f"HTTP {exc.status_code} | {request.method} {request.url.path} | {exc.detail}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": _status_to_error(exc.status_code),
            "detail": exc.detail,
            "path": str(request.url.path),
        },
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handles Pydantic validation errors with field-level detail."""
    errors = [
        {
            "field": " → ".join(str(l) for l in err["loc"]),
            "message": err["msg"],
            "type": err["type"],
        }
        for err in exc.errors()
    ]
    logger.warning(
        f"Validation error | {request.method} {request.url.path} | {errors}"
    )
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "detail": "Request body validation failed",
            "errors": errors,
            "path": str(request.url.path),
        },
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Catches anything not handled above — never leaks stack traces."""
    logger.error(
        f"Unhandled exception | {request.method} {request.url.path} | {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": "An unexpected error occurred",
            "path": str(request.url.path),
        },
    )


def _status_to_error(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        422: "validation_error",
        429: "rate_limit_exceeded",
        500: "internal_server_error",
        501: "not_implemented",
        503: "service_unavailable",
    }.get(status_code, "error")