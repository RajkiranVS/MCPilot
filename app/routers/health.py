"""
MCPilot — Health Router
Liveness + readiness endpoints.
Used by Docker health checks and AWS ECS in Week 4.
"""
import time
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/health", tags=["Health"])
_START_TIME = time.time()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    uptime_seconds: float


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, str]


@router.get("", response_model=HealthResponse, summary="Liveness check")
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name.lower(),
        version=settings.app_version,
        environment=settings.environment,
        uptime_seconds=round(time.time() - _START_TIME, 2),
    )


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness check")
async def readiness() -> ReadinessResponse:
    # TODO Week 2: real DB + ChromaDB ping
    return ReadinessResponse(
        status="ok",
        checks={
            "api": "ok",
            "database": "pending",      # BUILD-007
            "vector_store": "pending",  # BUILD-005
            "sagemaker": "pending",     # BUILD-009
        }
    )