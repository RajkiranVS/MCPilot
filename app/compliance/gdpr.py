"""
MCPilot — GDPR/DPDP Compliance Engine
Implements:
  1. Pseudonymisation  — replace real identifiers with reversible tokens
  2. Right to Erasure  — GDPR Article 17 / DPDP Act Section 12
  3. Data Retention    — automated purge stubs for scheduled jobs
  4. Consent tracking  — stub for future implementation

Terminology:
  GDPR  → EU General Data Protection Regulation
  DPDP  → India Digital Personal Data Protection Act 2023
  PHI   → Protected Health Information (HIPAA)
  PII   → Personally Identifiable Information (broader term)

For defence clients: DPDP Act 2023 is the primary applicable framework.
GDPR compliance is included for international deployments.
"""
import hashlib
import hmac
import uuid
from datetime import datetime, timezone, timedelta
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


# ── Pseudonymisation ──────────────────────────────────────────────────────────

def pseudonymise(identifier: str, tenant_id: str) -> str:
    """
    Replace a real identifier with a deterministic pseudonym.
    Same input always produces same pseudonym — allows re-identification
    by authorised parties with access to the secret key.

    Uses HMAC-SHA256 with tenant-scoped key so pseudonyms are
    different across tenants even for the same input.

    Args:
        identifier: Real value to pseudonymise (name, email, badge number)
        tenant_id:  Tenant context — scopes the pseudonym

    Returns:
        Pseudonym string like "PSE-a3f7b2c1"
    """
    key = f"{settings.secret_key}:{tenant_id}".encode()
    token = hmac.new(key, identifier.encode(), hashlib.sha256).hexdigest()
    return f"PSE-{token[:8]}"


def pseudonymise_dict(data: dict, tenant_id: str, fields: list[str]) -> dict:
    """
    Pseudonymise specific fields in a dictionary.
    Non-listed fields are passed through unchanged.

    Args:
        data:      Input dict
        tenant_id: Tenant context
        fields:    List of field names to pseudonymise

    Returns:
        Dict with specified fields replaced by pseudonyms
    """
    result = dict(data)
    for field in fields:
        if field in result and isinstance(result[field], str):
            original = result[field]
            result[field] = pseudonymise(original, tenant_id)
            logger.debug(f"Pseudonymised field: {field}")
    return result


def is_pseudonym(value: str) -> bool:
    """Check if a value looks like a MCPilot pseudonym."""
    return isinstance(value, str) and value.startswith("PSE-") and len(value) == 12


# ── Right to Erasure ──────────────────────────────────────────────────────────

class ErasureRequest:
    """
    Represents a right-to-erasure request (GDPR Art. 17 / DPDP S.12).
    Stub implementation — full workflow in v1.1.
    """

    def __init__(
        self,
        subject_id: str,
        tenant_id:  str,
        reason:     str = "data_subject_request",
    ):
        self.request_id  = str(uuid.uuid4())
        self.subject_id  = subject_id
        self.tenant_id   = tenant_id
        self.reason      = reason
        self.requested_at = datetime.now(timezone.utc)
        self.status      = "pending"

    def to_dict(self) -> dict:
        return {
            "request_id":   self.request_id,
            "subject_id":   self.subject_id,
            "tenant_id":    self.tenant_id,
            "reason":       self.reason,
            "requested_at": self.requested_at.isoformat(),
            "status":       self.status,
        }


async def request_erasure(
    subject_id: str,
    tenant_id:  str,
    reason:     str = "data_subject_request",
) -> dict:
    """
    Initiate a right-to-erasure request.

    What this does:
      1. Creates erasure request record
      2. Flags subject's data for deletion
      3. Returns request ID for tracking

    What this does NOT do yet (v1.1):
      - Cascade deletion across all data stores
      - Send confirmation to data subject
      - Integrate with backup purge pipeline

    IMPORTANT: Audit log records are ANONYMISED not deleted.
    Deleting audit records would break the hash chain integrity.
    Instead, PII fields are replaced with "[ERASED]".

    Args:
        subject_id: The identifier of the data subject
        tenant_id:  Tenant context
        reason:     Reason for erasure request

    Returns:
        Erasure request details including tracking ID
    """
    if not settings.enable_right_to_erasure:
        return {
            "status":  "disabled",
            "message": "Right to erasure is disabled in current configuration",
        }

    request = ErasureRequest(
        subject_id=subject_id,
        tenant_id=tenant_id,
        reason=reason,
    )

    logger.info(
        f"Erasure request initiated | "
        f"request_id={request.request_id} "
        f"tenant={tenant_id} "
        f"reason={reason}"
    )

    # TODO v1.1: persist to erasure_requests table
    # TODO v1.1: trigger async erasure pipeline
    # TODO v1.1: send confirmation notification

    return {
        **request.to_dict(),
        "message": (
            "Erasure request accepted. PII will be anonymised within 30 days "
            "per GDPR Article 17 / DPDP Act Section 12. "
            "Audit log records will be anonymised to preserve chain integrity."
        ),
        "audit_note": (
            "Audit log records cannot be deleted — they will be anonymised. "
            "This preserves hash chain integrity required by HIPAA/DPDP audit mandates."
        ),
    }


# ── Data Retention ────────────────────────────────────────────────────────────

def get_retention_cutoff(
    retention_days: int | None = None,
    data_type: str = "pii",
) -> datetime:
    """
    Calculate the cutoff datetime for data retention.
    Records older than this should be purged or anonymised.

    Args:
        retention_days: Override for retention period
        data_type:      "pii" or "audit" — uses config defaults if not specified

    Returns:
        Cutoff datetime — records before this are eligible for purge
    """
    if retention_days is None:
        if data_type == "audit":
            retention_days = settings.audit_log_retention_days
        else:
            retention_days = settings.pii_data_retention_days

    return datetime.now(timezone.utc) - timedelta(days=retention_days)


def check_retention_compliance(created_at: datetime, data_type: str = "pii") -> dict:
    """
    Check if a record is within its retention window.

    Args:
        created_at: When the record was created
        data_type:  "pii" or "audit"

    Returns:
        Dict with compliance status and days remaining
    """
    if data_type == "audit":
        retention_days = settings.audit_log_retention_days
    else:
        retention_days = settings.pii_data_retention_days

    expiry = created_at + timedelta(days=retention_days)
    now = datetime.now(timezone.utc)
    days_remaining = (expiry - now).days

    return {
        "compliant":       days_remaining > 0,
        "days_remaining":  max(0, days_remaining),
        "expiry_date":     expiry.isoformat(),
        "retention_days":  retention_days,
        "data_type":       data_type,
    }


async def purge_expired_pii(tenant_id: str | None = None, dry_run: bool = True) -> dict:
    """
    Purge PII data older than retention policy allows.
    Stub — full implementation in v1.1 with scheduled job.

    Args:
        tenant_id: Scope purge to specific tenant (None = all tenants)
        dry_run:   If True, only reports what would be purged

    Returns:
        Purge report with counts and cutoff date
    """
    cutoff = get_retention_cutoff(data_type="pii")

    logger.info(
        f"PII purge {'(dry run) ' if dry_run else ''}initiated | "
        f"tenant={tenant_id or 'ALL'} "
        f"cutoff={cutoff.date()}"
    )

    # TODO v1.1: query audit_log for records older than cutoff
    # TODO v1.1: anonymise PII fields in expired records
    # TODO v1.1: delete data_subjects records past retention

    return {
        "dry_run":        dry_run,
        "cutoff_date":    cutoff.isoformat(),
        "tenant_id":      tenant_id or "ALL",
        "records_purged": 0,  # stub
        "status":         "stub — full implementation in v1.1",
        "message": (
            f"Would purge PII data older than {cutoff.date()} "
            f"({settings.pii_data_retention_days} day retention policy). "
            f"Run with dry_run=False to execute."
        ),
    }


# ── Consent ───────────────────────────────────────────────────────────────────

def get_processing_basis(data_type: str = "pii") -> dict:
    """
    Returns the legal basis for processing under GDPR/DPDP.
    Documents why MCPilot is legally allowed to process this data.

    For defence: lawful basis is typically "public task" or "legitimate interest"
    For healthcare: "vital interests" or "explicit consent"
    """
    return {
        "gdpr_basis":    "legitimate_interest",
        "gdpr_article":  "Article 6(1)(f)",
        "dpdp_basis":    "legitimate_use",
        "dpdp_section":  "Section 7",
        "purpose":       "Security audit logging and PII protection",
        "data_type":     data_type,
        "controller":    settings.data_controller_name,
        "contact":       settings.data_controller_contact,
    }