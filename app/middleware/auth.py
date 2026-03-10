"""
MCPilot — Auth Middleware Stub
JWT + API key validation. Stub until BUILD-002.
"""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logging import get_logger

logger = get_logger(__name__)

PUBLIC_PATHS = {"/health", "/health/ready", "/docs", "/openapi.json", "/redoc", "/"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        # TODO BUILD-002: JWT decode + API key lookup
        logger.debug(f"Auth stub — passing through: {request.url.path}")
        return await call_next(request)