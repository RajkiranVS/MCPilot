"""
MCPilot — Classification Registry Router
Exposes clearance registry state and gating decisions via REST API.

Endpoints:
  GET  /gateway/classification/tenants          — list all tenant clearances
  GET  /gateway/classification/servers          — list all server classifications
  POST /gateway/classification/gate             — test a gating decision
  GET  /gateway/classification/tenant/{id}      — single tenant profile
  GET  /gateway/classification/server/{id}      — single server profile
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from app.compliance.classification import (
    registry as clearance_registry,
    ClassificationLevel,
    ClearanceLevel,
)
from app.core.logging import get_logger

router = APIRouter(prefix="/gateway/classification", tags=["Classification"])
logger = get_logger(__name__)


# ── Request / Response models ─────────────────────────────────────────────────

class GateRequest(BaseModel):
    requestor_tenant:    str
    target_server:       str
    data_classification: Optional[str] = None  # override, e.g. "SECRET"

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Navy ops → intel server",
                    "value": {
                        "requestor_tenant": "navy-ops",
                        "target_server":    "intel",
                    }
                },
                {
                    "title": "ICG watchkeeper → SIGINT override",
                    "value": {
                        "requestor_tenant":    "icg-watchkeeper",
                        "target_server":       "maritime",
                        "data_classification": "SECRET",
                    }
                },
            ]
        }
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/tenants", summary="List all tenant clearance profiles")
async def list_tenants(request: Request) -> dict:
    """
    Returns all registered tenant clearance profiles.
    Shows tenant_id, name, clearance level, unit and colour code.
    """
    tenants = clearance_registry.list_tenants()

    # Enrich with colour and numeric level
    for t in tenants:
        level = ClearanceLevel[t["clearance"]]
        t["clearance_value"] = level.value
        t["clearance_colour"] = ClassificationLevel(level.value).colour

    return {
        "total":   len(tenants),
        "tenants": tenants,
    }


@router.get("/servers", summary="List all server classification profiles")
async def list_servers(request: Request) -> dict:
    """
    Returns all registered MCP server classification profiles.
    Shows server_id, name, classification level and colour code.
    """
    servers = clearance_registry.list_servers()

    # Enrich with colour and numeric level
    for s in servers:
        level = ClassificationLevel[s["classification"]]
        s["classification_value"] = level.value
        s["classification_colour"] = level.colour

    return {
        "total":   len(servers),
        "servers": servers,
    }


@router.get("/tenant/{tenant_id}", summary="Get single tenant clearance profile")
async def get_tenant(tenant_id: str, request: Request) -> dict:
    """Returns clearance profile for a specific tenant."""
    profile = clearance_registry.get_tenant(tenant_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"Tenant '{tenant_id}' not found in clearance registry"
        )
    level = profile.clearance
    return {
        "tenant_id":       profile.tenant_id,
        "name":            profile.name,
        "clearance":       level.name,
        "clearance_value": level.value,
        "clearance_colour": ClassificationLevel(level.value).colour,
        "unit":            profile.unit,
        "description":     profile.description,
    }


@router.get("/server/{server_id}", summary="Get single server classification profile")
async def get_server(server_id: str, request: Request) -> dict:
    """Returns classification profile for a specific MCP server."""
    profile = clearance_registry.get_server(server_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"Server '{server_id}' not found in classification registry"
        )
    level = profile.default_classification
    return {
        "server_id":              profile.server_id,
        "name":                   profile.name,
        "classification":         level.name,
        "classification_value":   level.value,
        "classification_colour":  level.colour,
        "description":            profile.description,
    }


@router.post("/gate", summary="Test a classification gating decision")
async def test_gate(payload: GateRequest, request: Request) -> dict:
    """
    Simulate a classification gate check without executing a tool call.
    Useful for dashboard previews and integration testing.

    Returns the full GatingDecision including action, reason and audit hash.
    """
    # Validate tenant exists
    if not clearance_registry.get_tenant(payload.requestor_tenant):
        raise HTTPException(
            status_code=404,
            detail=f"Tenant '{payload.requestor_tenant}' not found"
        )

    # Validate server exists
    if not clearance_registry.get_server(payload.target_server):
        raise HTTPException(
            status_code=404,
            detail=f"Server '{payload.target_server}' not found"
        )

    # Parse optional classification override
    override = None
    if payload.data_classification:
        try:
            override = ClassificationLevel.from_str(payload.data_classification)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid classification level: '{payload.data_classification}'. "
                       f"Valid values: {[l.name for l in ClassificationLevel]}"
            )

    decision = clearance_registry.gate(
        requestor_tenant=payload.requestor_tenant,
        target_server=payload.target_server,
        data_classification=override,
    )

    logger.info(
        f"Gate test | tenant={payload.requestor_tenant} "
        f"server={payload.target_server} action={decision.action}"
    )

    return {
        "decision":           decision.to_dict(),
        "tenant_profile":     {
            "tenant_id":  payload.requestor_tenant,
            "clearance":  decision.requestor_clearance.name,
            "colour":     ClassificationLevel(decision.requestor_clearance.value).colour,
        },
        "server_profile": {
            "server_id":      payload.target_server,
            "classification": decision.data_classification.name,
            "colour":         decision.data_classification.colour,
        },
        "summary": (
            f"{decision.requestor_clearance.name} clearance "
            f"{'✓ ACCESS GRANTED' if decision.passed else '⚠ REDACTED' if decision.requires_redaction else '✗ ACCESS DENIED'} "
            f"to {decision.data_classification.name} server"
        ),
    }


@router.get("/matrix", summary="Full clearance vs classification access matrix")
async def access_matrix(request: Request) -> dict:
    """
    Returns a complete matrix showing what each tenant can access on each server.
    Used by the classification dashboard to render the access grid.
    """
    tenants = clearance_registry.list_tenants()
    servers = clearance_registry.list_servers()

    matrix = []
    for tenant in tenants:
        row = {
            "tenant_id":  tenant["tenant_id"],
            "name":       tenant["name"],
            "clearance":  tenant["clearance"],
            "access":     {}
        }
        for server in servers:
            decision = clearance_registry.gate(
                requestor_tenant=tenant["tenant_id"],
                target_server=server["server_id"],
            )
            row["access"][server["server_id"]] = {
                "action":  decision.action,
                "colour":  (
                    "#00FF88" if decision.passed
                    else "#F5A623" if decision.requires_redaction
                    else "#FF3344"
                ),
            }
        matrix.append(row)

    return {
        "tenants": [t["tenant_id"] for t in tenants],
        "servers": [s["server_id"] for s in servers],
        "matrix":  matrix,
    }