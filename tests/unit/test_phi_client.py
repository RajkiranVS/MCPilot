"""
MCPilot — PHI Client unit tests
Tests local spaCy path (development mode).
SageMaker path tested via integration test after endpoint deploy.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.compliance.phi_client import PHIClient


@pytest.fixture
def local_client():
    """PHI client in development mode — uses local spaCy."""
    with patch("app.compliance.phi_client.settings") as mock_settings:
        mock_settings.environment = "development"
        mock_settings.aws_sagemaker_phi_endpoint = ""
        mock_settings.aws_region = "ap-south-1"
        client = PHIClient()
    return client


def test_phi_client_uses_local_in_dev(local_client):
    assert local_client._use_sagemaker is False


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


def test_phi_client_sagemaker_mode():
    """Verify SageMaker mode is activated in production with endpoint set."""
    with patch("app.compliance.phi_client.settings") as mock_settings:
        with patch("app.compliance.phi_client.boto3") as mock_boto3:
            mock_settings.environment = "production"
            mock_settings.aws_sagemaker_phi_endpoint = "mcpilot-phi-detector"
            mock_settings.aws_region = "ap-south-1"
            mock_boto3.client.return_value = MagicMock()
            client = PHIClient()
    assert client._use_sagemaker is True