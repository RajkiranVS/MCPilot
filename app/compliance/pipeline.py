"""
MCPilot — PHI Compliance Pipeline
Orchestrates PHI scanning on tool call inputs and outputs.

Called from the gateway router on every tool invocation:
  1. scan_input()   → scans parameters before tool call
  2. scan_output()  → scans tool response after execution

Returns redacted data + compliance metadata for audit logging (BUILD-011).
"""
from dataclasses import dataclass
from app.compliance.phi_client import phi_client
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ComplianceResult:
    """Compliance scan result for one direction (input or output)."""
    original:       dict | list | str
    redacted:       dict | list | str
    phi_detected:   bool
    entity_count:   int
    redacted_count: int
    direction:      str   # "input" or "output"

def scan_input(parameters: dict) -> ComplianceResult:
    """
    Sync PII scan using spaCy — used by gateway tool calls and tests.
    For the /gateway/query demo endpoint use scan_input_async (LLM-based).
    """
    if not parameters:
        return ComplianceResult(
            original={}, redacted={}, phi_detected=False,
            entity_count=0, redacted_count=0, direction="input",
        )

    redacted, any_pii = phi_client.scan_dict(parameters)

    if any_pii:
        logger.warning(
            "PII detected in tool call input — parameters redacted before dispatch"
        )

    return ComplianceResult(
        original=parameters,
        redacted=redacted,
        phi_detected=any_pii,
        entity_count=_count_entities(parameters),
        redacted_count=_count_redacted(parameters, redacted),
        direction="input",
    )


async def scan_input_async(parameters: dict) -> ComplianceResult:
    """
    Async version of scan_input — uses LLM-based PHI detection.
    Catches badge numbers, military IDs, rank+name combinations.
    """
    from app.compliance.phi_detector import detect_with_llm

    if not parameters:
        return ComplianceResult(
            original={}, redacted={}, phi_detected=False,
            entity_count=0, redacted_count=0, direction="input",
        )

    redacted = {}
    any_phi = False

    for key, value in parameters.items():
        if isinstance(value, str):
            result = await detect_with_llm(value)
            redacted[key] = result.redacted_text
            if result.phi_detected:
                any_phi = True
        else:
            redacted[key] = value

    return ComplianceResult(
        original=parameters,
        redacted=redacted,
        phi_detected=any_phi,
        entity_count=0,
        redacted_count=0,
        direction="input",
    )


def scan_output(result: dict) -> ComplianceResult:
    """
    Scan tool response for PHI before returning to client.
    Scans the content blocks inside the MCP result dict.

    Args:
        result: MCP tool response dict with 'content' and 'is_error' keys

    Returns:
        ComplianceResult with redacted response and detection metadata
    """
    if not result:
        return ComplianceResult(
            original={},
            redacted={},
            phi_detected=False,
            entity_count=0,
            redacted_count=0,
            direction="output",
        )

    # Scan the content blocks
    content = result.get("content", [])
    redacted_content = []
    any_phi = False

    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            detection = phi_client.detect(block.get("text", ""))
            redacted_block = {**block, "text": detection.redacted_text}
            redacted_content.append(redacted_block)
            if detection.phi_detected:
                any_phi = True
        else:
            redacted_content.append(block)

    redacted_result = {**result, "content": redacted_content}

    if any_phi:
        logger.warning(
            "PHI detected in tool response — content redacted before returning to client"
        )

    return ComplianceResult(
        original=result,
        redacted=redacted_result,
        phi_detected=any_phi,
        entity_count=0,
        redacted_count=0,
        direction="output",
    )


def _count_entities(data: dict) -> int:
    """Count total string values in a dict for baseline metrics."""
    count = 0
    for v in data.values():
        if isinstance(v, str):
            count += 1
        elif isinstance(v, dict):
            count += _count_entities(v)
    return count


def _count_redacted(original: dict, redacted: dict) -> int:
    """Count how many string values were changed by redaction."""
    count = 0
    for k in original:
        if isinstance(original[k], str) and original[k] != redacted.get(k):
            count += 1
        elif isinstance(original[k], dict):
            count += _count_redacted(original[k], redacted.get(k, {}))
    return count