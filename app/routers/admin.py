"""
MCPilot — Admin Router
Tenant and API key management.
Protected by admin scope.
"""
import secrets
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from app.core.logging import get_logger
from app.db.base import get_session_factory
from app.db.repository import TenantRepository

router = APIRouter(prefix="/admin", tags=["Admin"])
logger = get_logger(__name__)


def _require_admin(request: Request):
    scopes = getattr(request.state, "scopes", [])
    if "admin" not in scopes:
        raise HTTPException(status_code=403, detail="Admin scope required")


class CreateTenantRequest(BaseModel):
    tenant_id: str
    name:      str
    plan:      str = "standard"


class CreateAPIKeyRequest(BaseModel):
    tenant_id: str
    client_id: str
    scopes:    list[str] = ["gateway:invoke"]


@router.post("/tenants", summary="Create a new tenant")
async def create_tenant(body: CreateTenantRequest, request: Request) -> dict:
    _require_admin(request)
    factory = get_session_factory()
    async with factory() as session:
        repo = TenantRepository(session)
        tenant = await repo.create_tenant(
            tenant_id=body.tenant_id,
            name=body.name,
            plan=body.plan,
        )
        await session.commit()
        return {
            "tenant_id": tenant.tenant_id,
            "name":      tenant.name,
            "plan":      tenant.plan,
            "active":    tenant.active,
            "created_at": tenant.created_at.isoformat(),
        }


@router.get("/tenants", summary="List all tenants")
async def list_tenants(request: Request) -> dict:
    _require_admin(request)
    factory = get_session_factory()
    async with factory() as session:
        repo = TenantRepository(session)
        tenants = await repo.list_tenants()
        return {
            "tenants": [
                {
                    "tenant_id": t.tenant_id,
                    "name":      t.name,
                    "plan":      t.plan,
                    "active":    t.active,
                }
                for t in tenants
            ],
            "total": len(tenants),
        }


@router.post("/api-keys", summary="Create API key for tenant")
async def create_api_key(body: CreateAPIKeyRequest, request: Request) -> dict:
    _require_admin(request)

    # Generate a secure random API key
    raw_key = f"mcpilot-{secrets.token_urlsafe(24)}"

    factory = get_session_factory()
    async with factory() as session:
        repo = TenantRepository(session)
        api_key = await repo.create_api_key(
            tenant_id=body.tenant_id,
            client_id=body.client_id,
            raw_key=raw_key,
            scopes=body.scopes,
        )
        await session.commit()
        return {
            "api_key":   raw_key,   # shown ONCE — store securely
            "prefix":    api_key.key_prefix,
            "tenant_id": body.tenant_id,
            "client_id": body.client_id,
            "scopes":    body.scopes,
            "warning":   "Store this key securely — it will not be shown again",
        }


@router.delete("/api-keys/{key_prefix}", summary="Deactivate an API key")
async def deactivate_api_key(
    key_prefix: str,
    tenant_id:  str,
    request:    Request,
) -> dict:
    _require_admin(request)
    factory = get_session_factory()
    async with factory() as session:
        repo = TenantRepository(session)
        success = await repo.deactivate_api_key(key_prefix, tenant_id)
        await session.commit()
        if not success:
            raise HTTPException(status_code=404, detail="API key not found")
        return {"status": "deactivated", "prefix": key_prefix}