"""
MCPilot — GDPR/DPDP Compliance unit tests
"""
import pytest
from datetime import datetime, timezone, timedelta
from app.compliance.gdpr import (
    pseudonymise,
    pseudonymise_dict,
    is_pseudonym,
    ErasureRequest,
    get_retention_cutoff,
    check_retention_compliance,
    get_processing_basis,
)


# ── Pseudonymisation ──────────────────────────────────────────────────────────
def test_pseudonymise_returns_pse_prefix():
    result = pseudonymise("John Smith", "tenant-1")
    assert result.startswith("PSE-")


def test_pseudonymise_deterministic():
    r1 = pseudonymise("John Smith", "tenant-1")
    r2 = pseudonymise("John Smith", "tenant-1")
    assert r1 == r2


def test_pseudonymise_different_tenants():
    r1 = pseudonymise("John Smith", "tenant-1")
    r2 = pseudonymise("John Smith", "tenant-2")
    assert r1 != r2


def test_pseudonymise_different_inputs():
    r1 = pseudonymise("John Smith", "tenant-1")
    r2 = pseudonymise("Jane Doe", "tenant-1")
    assert r1 != r2


def test_pseudonymise_length():
    result = pseudonymise("Major Ram Prasad Sharma", "tenant-1")
    assert len(result) == 12  # "PSE-" + 8 hex chars


def test_pseudonymise_dict_replaces_fields():
    data = {"name": "John Smith", "query": "sector-4 logs", "limit": 10}
    result = pseudonymise_dict(data, "tenant-1", fields=["name"])
    assert result["name"].startswith("PSE-")
    assert result["query"] == "sector-4 logs"
    assert result["limit"] == 10


def test_pseudonymise_dict_multiple_fields():
    data = {"name": "John Smith", "email": "john@example.com"}
    result = pseudonymise_dict(data, "tenant-1", fields=["name", "email"])
    assert result["name"].startswith("PSE-")
    assert result["email"].startswith("PSE-")


def test_is_pseudonym_true():
    p = pseudonymise("test", "tenant-1")
    assert is_pseudonym(p) is True


def test_is_pseudonym_false():
    assert is_pseudonym("John Smith") is False
    assert is_pseudonym("") is False
    assert is_pseudonym("PSE-short") is False   # 9 chars — too short
    assert is_pseudonym("PSE-") is False         # no hash at all
    assert is_pseudonym("XYZ-a3f7b2c1") is False # wrong prefix


# ── Erasure Request ───────────────────────────────────────────────────────────
def test_erasure_request_creates_id():
    req = ErasureRequest("subject-1", "tenant-1")
    assert req.request_id is not None
    assert len(req.request_id) == 36


def test_erasure_request_status_pending():
    req = ErasureRequest("subject-1", "tenant-1")
    assert req.status == "pending"


def test_erasure_request_to_dict():
    req = ErasureRequest("subject-1", "tenant-1", "test_reason")
    d = req.to_dict()
    assert d["subject_id"] == "subject-1"
    assert d["tenant_id"] == "tenant-1"
    assert d["reason"] == "test_reason"
    assert d["status"] == "pending"
    assert "request_id" in d
    assert "requested_at" in d


# ── Retention ─────────────────────────────────────────────────────────────────
def test_retention_cutoff_pii():
    cutoff = get_retention_cutoff(data_type="pii")
    assert isinstance(cutoff, datetime)
    assert cutoff < datetime.now(timezone.utc)


def test_retention_cutoff_audit():
    cutoff = get_retention_cutoff(data_type="audit")
    assert isinstance(cutoff, datetime)
    assert cutoff < datetime.now(timezone.utc)


def test_retention_cutoff_audit_older_than_pii():
    audit_cutoff = get_retention_cutoff(data_type="audit")
    pii_cutoff   = get_retention_cutoff(data_type="pii")
    assert audit_cutoff < pii_cutoff


def test_check_retention_compliant():
    recent = datetime.now(timezone.utc) - timedelta(days=10)
    result = check_retention_compliance(recent, data_type="pii")
    assert result["compliant"] is True
    assert result["days_remaining"] > 0


def test_check_retention_expired():
    old = datetime.now(timezone.utc) - timedelta(days=400)
    result = check_retention_compliance(old, data_type="pii")
    assert result["compliant"] is False
    assert result["days_remaining"] == 0


def test_check_retention_audit_longer():
    # Audit records should have longer retention than PII
    from app.core.config import get_settings
    s = get_settings()
    assert s.audit_log_retention_days > s.pii_data_retention_days


# ── Processing Basis ──────────────────────────────────────────────────────────
def test_processing_basis_has_required_fields():
    basis = get_processing_basis()
    assert "gdpr_basis"   in basis
    assert "gdpr_article" in basis
    assert "dpdp_basis"   in basis
    assert "dpdp_section" in basis
    assert "controller"   in basis