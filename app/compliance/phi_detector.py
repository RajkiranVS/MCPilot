"""
MCPilot — PHI Detection + Redaction Pipeline
Core compliance engine for HIPAA PHI handling.

Two main operations:
  detect(text)  → returns list of PHI entities found
  redact(text)  → returns text with PHI replaced by typed placeholders

Redaction format: [PERSON], [SSN], [MRN], [DOB], [PHONE], [EMAIL]

Week 3: scan() and redact() will call AWS SageMaker endpoint
instead of local spaCy model when ENVIRONMENT=production.
"""
from dataclasses import dataclass
from app.compliance.phi_model import get_phi_model
from app.compliance.patterns import REDACT_LABELS, PHI_LABELS
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PHIEntity:
    """A detected PHI entity with location and type information."""
    text:       str    # original text
    label:      str    # entity type: PERSON, SSN, MRN, etc.
    start:      int    # character start position
    end:        int    # character end position
    redact:     bool   # whether this entity should be redacted
    label_name: str    # human-readable label name


@dataclass
class DetectionResult:
    """Result of running PHI detection on a text."""
    original_text:  str
    entities:       list[PHIEntity]
    phi_detected:   bool          # True if any redactable PHI found
    redacted_text:  str           # text with PHI replaced
    entity_count:   int
    redacted_count: int


def detect(text: str) -> DetectionResult:
    """
    Scan text for PHI entities.
    Returns DetectionResult with all detected entities and redacted text.

    Args:
        text: Input text to scan

    Returns:
        DetectionResult with:
          - entities: all PHI found (type, position, whether to redact)
          - redacted_text: text safe to pass downstream
          - phi_detected: True if any redactable PHI was found
    """
    if not text or not text.strip():
        return DetectionResult(
            original_text=text,
            entities=[],
            phi_detected=False,
            redacted_text=text,
            entity_count=0,
            redacted_count=0,
        )

    nlp = get_phi_model()
    doc = nlp(text)

    entities = []
    for ent in doc.ents:
        should_redact = ent.label_ in REDACT_LABELS
        entities.append(PHIEntity(
            text=ent.text,
            label=ent.label_,
            start=ent.start_char,
            end=ent.end_char,
            redact=should_redact,
            label_name=PHI_LABELS.get(ent.label_, ent.label_),
        ))

    redactable = [e for e in entities if e.redact]
    redacted_text = _redact_entities(text, redactable)

    result = DetectionResult(
        original_text=text,
        entities=entities,
        phi_detected=len(redactable) > 0,
        redacted_text=redacted_text,
        entity_count=len(entities),
        redacted_count=len(redactable),
    )

    if result.phi_detected:
        logger.warning(
            f"PHI detected | entities={result.redacted_count} "
            f"types={list(set(e.label for e in redactable))}"
        )

    return result


def _redact_entities(text: str, entities: list[PHIEntity]) -> str:
    """
    Replace PHI entities with typed placeholders.
    Works from end to start to preserve character positions.
    """
    # Sort by start position descending — replace from end to start
    sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)

    result = text
    for entity in sorted_entities:
        placeholder = f"[{entity.label}]"
        result = result[:entity.start] + placeholder + result[entity.end:]

    return result


def scan_dict(data: dict) -> tuple[dict, bool]:
    """
    Recursively scan a dictionary for PHI in string values.
    Returns (redacted_dict, phi_was_detected).
    Used to scan MCP tool call parameters and responses.
    """
    redacted = {}
    any_phi = False

    for key, value in data.items():
        if isinstance(value, str):
            result = detect(value)
            redacted[key] = result.redacted_text
            if result.phi_detected:
                any_phi = True
        elif isinstance(value, dict):
            redacted[key], child_phi = scan_dict(value)
            any_phi = any_phi or child_phi
        elif isinstance(value, list):
            redacted[key], child_phi = scan_list(value)
            any_phi = any_phi or child_phi
        else:
            redacted[key] = value

    return redacted, any_phi


def scan_list(data: list) -> tuple[list, bool]:
    """Recursively scan a list for PHI in string values."""
    redacted = []
    any_phi = False

    for item in data:
        if isinstance(item, str):
            result = detect(item)
            redacted.append(result.redacted_text)
            if result.phi_detected:
                any_phi = True
        elif isinstance(item, dict):
            redacted_item, child_phi = scan_dict(item)
            redacted.append(redacted_item)
            any_phi = any_phi or child_phi
        else:
            redacted.append(item)

    return redacted, any_phi