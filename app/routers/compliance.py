"""
MCPilot — Compliance API Router
GDPR Article 17 / DPDP Act 2023 endpoints.

Exposed under /compliance prefix.
All endpoints require authentication.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from app.compliance.gdpr import (
    pseudonymise,
    request_erasure,
    purge_expired_pii,
    get_retention_cutoff,
    check_retention_compliance,
    get_processing_basis,
)
from app.core.logging import get_logger
from datetime import datetime, timezone

router = APIRouter(prefix="/compliance", tags=["Compliance"])
logger = get_logger(__name__)


class ErasureRequestBody(BaseModel):
    subject_id: str
    reason:     str = "data_subject_request"


class PseudonymiseBody(BaseModel):
    identifier: str


@router.post("/pseudonymise", summary="Pseudonymise an identifier")
async def pseudonymise_identifier(
    body:    PseudonymiseBody,
    request: Request,
) -> dict:
    """
    Replace a real identifier with a tenant-scoped pseudonym.
    Same input always produces same pseudonym — deterministic and reversible
    by authorised parties.
    """
    tenant_id = getattr(request.state, "tenant_id", "unknown")
    pseudonym = pseudonymise(body.identifier, tenant_id)
    return {
        "pseudonym":  pseudonym,
        "tenant_id":  tenant_id,
        "note":       "Pseudonym is deterministic and tenant-scoped",
    }


@router.post("/erasure", summary="Request right to erasure")
async def erasure_request(
    body:    ErasureRequestBody,
    request: Request,
) -> dict:
    """
    Initiate a GDPR Article 17 / DPDP Section 12 erasure request.
    PII will be anonymised within 30 days. Audit records are
    anonymised (not deleted) to preserve hash chain integrity.
    """
    tenant_id = getattr(request.state, "tenant_id", "unknown")
    result = await request_erasure(
        subject_id=body.subject_id,
        tenant_id=tenant_id,
        reason=body.reason,
    )
    logger.info(
        f"Erasure request | tenant={tenant_id} subject={body.subject_id}"
    )
    return result


@router.get("/retention", summary="Data retention policy")
async def get_retention_policy(request: Request) -> dict:
    """
    Returns the active data retention policy for this tenant.
    Compliant with DPDP Act Section 8(7) storage limitation principle.
    """
    from app.core.config import get_settings
    settings = get_settings()
    tenant_id = getattr(request.state, "tenant_id", "unknown")

    return {
        "tenant_id":              tenant_id,
        "audit_retention_days":   settings.audit_log_retention_days,
        "pii_retention_days":     settings.pii_data_retention_days,
        "audit_cutoff":           get_retention_cutoff(data_type="audit").isoformat(),
        "pii_cutoff":             get_retention_cutoff(data_type="pii").isoformat(),
        "auto_purge_enabled":     False,
        "framework":              "GDPR Art. 5(1)(e) + DPDP Act 2023 S.8(7)",
        "data_controller":        settings.data_controller_name,
        "contact":                settings.data_controller_contact,
    }


@router.post("/purge/dry-run", summary="Preview PII purge (dry run)")
async def purge_dry_run(request: Request) -> dict:
    """
    Preview what would be purged under current retention policy.
    Does not delete anything — safe to run at any time.
    """
    tenant_id = getattr(request.state, "tenant_id", "unknown")
    return await purge_expired_pii(tenant_id=tenant_id, dry_run=True)


@router.get("/basis", summary="Legal basis for data processing")
async def processing_basis() -> dict:
    """
    Returns the legal basis for PII processing under GDPR and DPDP Act.
    Required for transparency obligations.
    """
    return get_processing_basis()


@router.get("/health", summary="Compliance system health")
async def compliance_health() -> dict:
    """Quick compliance status check."""
    from app.core.config import get_settings
    settings = get_settings()
    return {
        "pseudonymisation_enabled": settings.enable_pseudonymisation,
        "right_to_erasure_enabled": settings.enable_right_to_erasure,
        "audit_retention_days":     settings.audit_log_retention_days,
        "pii_retention_days":       settings.pii_data_retention_days,
        "frameworks":               ["GDPR", "DPDP Act 2023", "HIPAA"],
        "status":                   "operational",
    }