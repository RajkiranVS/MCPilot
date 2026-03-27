"""
MCPilot — PHI Pipeline unit tests
Tests scan_input() and scan_output() with clean and PHI-containing data.
"""
import pytest
from app.compliance.pipeline import scan_input, scan_output


# ── scan_input tests ──────────────────────────────────────────────────────────
def test_scan_input_clean_parameters():
    params = {"path": "./README.md", "encoding": "utf-8"}
    result = scan_input(params)
    assert result.phi_detected is False
    assert result.redacted == params
    assert result.direction == "input"


def test_scan_input_detects_phi_in_parameters():
    params = {"query": "find records for John Smith SSN 123-45-6789"}
    result = scan_input(params)
    assert result.phi_detected is True
    assert "John Smith" not in result.redacted["query"]
    assert "123-45-6789" not in result.redacted["query"]


def test_scan_input_empty_parameters():
    result = scan_input({})
    assert result.phi_detected is False
    assert result.redacted == {}


def test_scan_input_nested_parameters():
    params = {
        "filter": {
            "patient_name": "Jane Doe",
            "diagnosis": "hypertension",
        }
    }
    result = scan_input(params)
    assert result.phi_detected is True
    assert "Jane Doe" not in result.redacted["filter"]["patient_name"]
    assert result.redacted["filter"]["diagnosis"] == "hypertension"


def test_scan_input_preserves_non_string_values():
    params = {"limit": 10, "offset": 0, "active": True}
    result = scan_input(params)
    assert result.phi_detected is False
    assert result.redacted["limit"] == 10
    assert result.redacted["active"] is True


# ── scan_output tests ─────────────────────────────────────────────────────────
def test_scan_output_clean_result():
    result = {
        "content": [{"type": "text", "text": "The server is running normally."}],
        "is_error": False,
    }
    scan = scan_output(result)
    assert scan.phi_detected is False
    assert scan.redacted["content"][0]["text"] == "The server is running normally."


def test_scan_output_detects_phi_in_content():
    result = {
        "content": [
            {"type": "text", "text": "Patient John Smith DOB January 1 1980"}
        ],
        "is_error": False,
    }
    scan = scan_output(result)
    assert scan.phi_detected is True
    assert "John Smith" not in scan.redacted["content"][0]["text"]
    assert "[PERSON]" in scan.redacted["content"][0]["text"]


def test_scan_output_multiple_content_blocks():
    result = {
        "content": [
            {"type": "text", "text": "Clean text here."},
            {"type": "text", "text": "Contact john@example.com for details."},
        ],
        "is_error": False,
    }
    scan = scan_output(result)
    assert scan.phi_detected is True
    assert scan.redacted["content"][0]["text"] == "Clean text here."
    assert "john@example.com" not in scan.redacted["content"][1]["text"]


def test_scan_output_preserves_is_error():
    result = {
        "content": [{"type": "text", "text": "No PHI here"}],
        "is_error": True,
    }
    scan = scan_output(result)
    assert scan.redacted["is_error"] is True


def test_scan_output_empty_result():
    scan = scan_output({})
    assert scan.phi_detected is False


def test_scan_output_direction():
    scan = scan_output({"content": [], "is_error": False})
    assert scan.direction == "output"