"""
MCPilot — Rate Limiting
Uses slowapi (Starlette-compatible wrapper around limits library).
Limits are applied per client IP on all /gateway/* routes.
Tenant-aware limiting (by tenant_id) wired in BUILD-007
when request.state.tenant_id is reliably set from PostgreSQL.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.config import get_settings

settings = get_settings()

# ── Limiter instance — shared across the app ──────────────────────────────────
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[
        f"{settings.rate_limit_requests}/minute"
    ],
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom 429 response — consistent with MCPilot error envelope.
    Includes Retry-After header so clients know when to retry.
    """
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "detail": f"Too many requests. Limit: {exc.limit}",
            "retry_after_seconds": 60,
        },
        headers={"Retry-After": "60"},
    )