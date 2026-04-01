"""
MCPilot — Auth Middleware
Supports two auth schemes on every /gateway/* request:
  1. Bearer JWT  → Authorization: Bearer <token>
  2. API Key     → X-API-Key: <key>

Public paths bypass auth entirely (health, docs).
Tenant context is injected into request.state for downstream use.
"""
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from jose import JWTError
from app.core.security import decode_access_token
from app.core.logging import get_logger
from app.core.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

# ── Paths that never require auth ─────────────────────────────────────────────
PUBLIC_PATHS = {
    "/",
    "/health",
    "/health/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
    "/metrics/ws",      # WebSocket — auth handled via query param
}

# ── In-memory API key store ───────────────────────────────────────────────────
# Week 2: replaced with PostgreSQL lookup via tool registry
# Format: { "raw_key": {"tenant_id": "...", "scopes": [...], "client_id": "..."} }
_API_KEY_STORE: dict[str, dict] = {
    "mcpilot-dev-key-001": {
        "client_id": "dev-client",
        "tenant_id": "dev-tenant",
        "scopes":    ["gateway:invoke"],
    },
    "mcpilot-admin-key-001": {
        "client_id": "admin-client",
        "tenant_id": "dev-tenant",
        "scopes":    ["gateway:invoke", "admin"],
    },
}


def _unauthorized(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"error": "unauthorized", "detail": detail},
        headers={"WWW-Authenticate": "Bearer"},
    )


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # WebSocket upgrades cannot receive HTTP responses — the endpoint
        # handles its own auth via query param, so pass them straight through.
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        path = request.url.path

        # ── Public paths — pass through immediately ───────────────────────────
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # ── Protected paths — require auth ────────────────────────────────────
        auth_header = request.headers.get("Authorization", "")
        api_key = request.headers.get("X-API-Key", "")

        if auth_header.startswith("Bearer "):
            # ── JWT path ──────────────────────────────────────────────────────
            token = auth_header.removeprefix("Bearer ").strip()
            try:
                payload = decode_access_token(token)
                request.state.client_id = payload.sub
                request.state.tenant_id = payload.tenant_id
                request.state.scopes = payload.scopes
                request.state.auth_scheme = "jwt"
                logger.debug(
                    f"JWT auth OK | client={payload.sub} "
                    f"tenant={payload.tenant_id} path={path}"
                )
            except JWTError as e:
                logger.warning(f"JWT validation failed | path={path} | {e}")
                return _unauthorized("Invalid or expired token")

        elif api_key:
            # ── API key path ──────────────────────────────────────────────────────
            # Check in-memory store first (dev keys — always fast)
            key_data = _API_KEY_STORE.get(api_key)

            if not key_data:
                # Fall back to DB lookup for tenant-managed keys
                try:
                    from app.db.base import get_session_factory
                    from app.db.repository import TenantRepository
                    factory = get_session_factory()
                    async with factory() as session:
                        repo = TenantRepository(session)
                        key_data = await repo.lookup_api_key(api_key)
                        if key_data:
                            await session.commit()
                except Exception as e:
                    logger.error(f"DB API key lookup failed: {e}")
            
            if not key_data:
                logger.warning(f"Invalid API key | path={path}")
                return _unauthorized("Invalid API key")
            
            request.state.client_id  = key_data["client_id"]
            request.state.tenant_id  = key_data["tenant_id"]
            request.state.scopes     = key_data["scopes"]
            request.state.auth_scheme = "api_key"
            logger.debug(
                f"API key auth OK | client={key_data['client_id']} "
                f"tenant={key_data['tenant_id']} path={path}"
            )


        else:
            # ── No credentials provided ───────────────────────────────────────
            logger.warning(f"Missing credentials | path={path}")
            return _unauthorized(
                "Provide either 'Authorization: Bearer <token>' "
                "or 'X-API-Key: <key>'"
            )

        return await call_next(request)