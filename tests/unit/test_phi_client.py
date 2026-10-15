"""
MCPilot — PHI Client unit tests
Tests the local spaCy pipeline.
"""
import pytest
from app.compliance.phi_client import PHIClient


@pytest.fixture
def local_client():
    return PHIClient()


def test_phi_client_detects_phi(local_client):
    result = local_client.detect("Patient John Smith SSN 123-45-6789")
    assert result.phi_detected is True


def test_phi_client_clean_text(local_client):
    result = local_client.detect("The server is running normally.")
    assert result.phi_detected is False


def test_phi_client_scan_dict(local_client):
    data = {"name": "Jane Doe", "note": "No PHI here"}
    redacted, phi_found = local_client.scan_dict(data)
    assert phi_found is True
    assert "Jane Doe" not in redacted["name"]
    assert redacted["note"] == "No PHI here"

