"""
MCPilot — PHI Detection + Redaction unit tests
Tests cover: person names, SSN, MRN, DOB, phone, email,
nested dict scanning, and edge cases.
"""
import pytest
from app.compliance.phi_detector import detect, scan_dict, scan_list


# ── Person name detection ─────────────────────────────────────────────────────
def test_detects_person_name():
    result = detect("Patient John Smith was admitted today.")
    persons = [e for e in result.entities if e.label == "PERSON"]
    assert len(persons) >= 1
    assert result.phi_detected is True


def test_redacts_person_name():
    result = detect("Contact Dr. Sarah Johnson for details.")
    assert "Sarah Johnson" not in result.redacted_text
    assert "[PERSON]" in result.redacted_text


# ── SSN detection ─────────────────────────────────────────────────────────────
def test_detects_ssn_with_dashes():
    result = detect("SSN: 123-45-6789")
    ssns = [e for e in result.entities if e.label == "SSN"]
    assert len(ssns) >= 1
    assert result.phi_detected is True


def test_redacts_ssn():
    result = detect("Patient SSN is 123-45-6789.")
    assert "123-45-6789" not in result.redacted_text
    assert "[SSN]" in result.redacted_text


# ── MRN detection ─────────────────────────────────────────────────────────────
def test_detects_mrn():
    result = detect("Medical record MRN1234567 was updated.")
    mrns = [e for e in result.entities if e.label == "MRN"]
    assert len(mrns) >= 1
    assert result.phi_detected is True


def test_redacts_mrn():
    result = detect("Patient MRN1234567 discharged.")
    assert "MRN1234567" not in result.redacted_text
    assert "[MRN]" in result.redacted_text


# ── DOB detection ─────────────────────────────────────────────────────────────
def test_detects_dob_with_context():
    result = detect("Patient born January 15, 1980 presents with symptoms.")
    dob_entities = [e for e in result.entities if e.label == "DOB"]
    assert len(dob_entities) >= 1


def test_detects_dob_keyword():
    result = detect("DOB: 03/15/1990")
    assert result.entity_count >= 1


# ── Phone detection ───────────────────────────────────────────────────────────
def test_detects_phone_number():
    result = detect("Call the patient at 555-123-4567.")
    phones = [e for e in result.entities if e.label == "PHONE"]
    assert len(phones) >= 1
    assert result.phi_detected is True


def test_redacts_phone_number():
    result = detect("Emergency contact: 555-123-4567.")
    assert "555-123-4567" not in result.redacted_text
    assert "[PHONE]" in result.redacted_text


# ── Email detection ───────────────────────────────────────────────────────────
def test_detects_email():
    result = detect("Send records to patient@example.com")
    emails = [e for e in result.entities if e.label == "EMAIL"]
    assert len(emails) >= 1
    assert result.phi_detected is True


def test_redacts_email():
    result = detect("Email: john.doe@hospital.org")
    assert "john.doe@hospital.org" not in result.redacted_text
    assert "[EMAIL]" in result.redacted_text


# ── Clean text ────────────────────────────────────────────────────────────────
def test_clean_text_no_phi():
    result = detect("The weather today is sunny and warm.")
    assert result.phi_detected is False
    assert result.redacted_text == "The weather today is sunny and warm."


def test_empty_text():
    result = detect("")
    assert result.phi_detected is False
    assert result.entities == []


def test_none_like_empty():
    result = detect("   ")
    assert result.phi_detected is False


# ── Result shape ──────────────────────────────────────────────────────────────
def test_detection_result_shape():
    result = detect("Patient John Smith, SSN 123-45-6789.")
    assert hasattr(result, "original_text")
    assert hasattr(result, "entities")
    assert hasattr(result, "phi_detected")
    assert hasattr(result, "redacted_text")
    assert hasattr(result, "entity_count")
    assert hasattr(result, "redacted_count")
    assert result.redacted_count <= result.entity_count


# ── Dict scanning ─────────────────────────────────────────────────────────────
def test_scan_dict_redacts_string_values():
    data = {
        "patient_name": "John Smith",
        "diagnosis":    "Hypertension",
        "contact":      "Call 555-123-4567",
    }
    redacted, phi_found = scan_dict(data)
    assert phi_found is True
    assert "John Smith" not in redacted["patient_name"]
    assert "555-123-4567" not in redacted["contact"]
    assert redacted["diagnosis"] == "Hypertension"


def test_scan_dict_nested():
    data = {
        "patient": {
            "name":  "Jane Doe",
            "email": "jane@example.com",
        },
        "notes": "No PHI here",
    }
    redacted, phi_found = scan_dict(data)
    assert phi_found is True
    assert "Jane Doe"        not in redacted["patient"]["name"]
    assert "jane@example.com" not in redacted["patient"]["email"]
    assert redacted["notes"] == "No PHI here"


def test_scan_dict_no_phi():
    data = {"query": "fetch the latest news", "limit": 10}
    redacted, phi_found = scan_dict(data)
    assert phi_found is False
    assert redacted["query"] == "fetch the latest news"


def test_scan_list_redacts_strings():
    data = ["Contact john@example.com", "No PHI here", "SSN: 123-45-6789"]
    redacted, phi_found = scan_list(data)
    assert phi_found is True
    assert "john@example.com" not in redacted[0]
    assert redacted[1] == "No PHI here"
    assert "123-45-6789" not in redacted[2]