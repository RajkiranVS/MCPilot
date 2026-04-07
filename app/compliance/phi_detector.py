"""
MCPilot — PHI Detection + Redaction Pipeline

Architecture (clean, no patches):
  Tier 1: Regex scan — deterministic, military-aware, fast (~2ms)
          Handles: callsigns, service numbers, rank+name, coords,
                   facilities, unit strength, military time, areas,
                   SSN, phone, email, badge, DOB
  Tier 2: spaCy NER on pre-masked text — plain names only (~20ms)
          Handles: John Smith, Sarah Johnson, Jane Doe
          Does NOT see already-detected spans → no misclassification
  Tier 3: LLM via Ollama — novel patterns only (~4.7s, cached)

Key insight: mask Tier 1 detections before running spaCy.
spaCy never sees service numbers, callsigns, coordinates → never
misclassifies them as PERSON/ORG/GPE.
"""
import re
import json
from dataclasses import dataclass
from app.compliance.phi_model import get_phi_model
from app.compliance.patterns import (
    REDACT_LABELS, PHI_LABELS, MILITARY_RANKS, BADGE_REGEX, BADGE_CONTEXT_REGEX,
    COORD_REGEX, UNIT_STRENGTH_REGEX, FACILITY_REGEX,
    MILITARY_TIME_REGEX, CALLSIGN_REGEX, AREA_REGEX,
    RANK_NAME_REGEX, SERVICE_NUMBER_REGEX,
    SSN_REGEX, PHONE_REGEX, EMAIL_REGEX, DOB_REGEX, MRN_REGEX, LOCATION_NAMES,
)
from app.compliance.cache import pii_cache
from app.core.logging import get_logger
from app.core.llm import complete

logger = get_logger(__name__)


@dataclass
class PHIEntity:
    """A detected PHI entity with location and type information."""
    text:       str
    label:      str
    start:      int
    end:        int
    redact:     bool
    label_name: str


@dataclass
class DetectionResult:
    """Result of running PHI detection on a text."""
    original_text:  str
    entities:       list[PHIEntity]
    phi_detected:   bool
    redacted_text:  str
    entity_count:   int
    redacted_count: int


# ── Tier 1: Regex scan ────────────────────────────────────────────────────────

def _regex_scan(text: str) -> list[PHIEntity]:
    """
    Deterministic regex scan — runs first, highest priority.
    Order matters: more specific patterns before general ones.
    """
    covered: set[tuple[int, int]] = set()
    entities: list[PHIEntity] = []

    def add(m: re.Match, label: str) -> None:
        start, end = m.start(), m.end()
        # Skip if overlaps with already-detected span
        if any(s <= start < e or s < end <= e for s, e in covered):
            return
        entities.append(PHIEntity(
            text=m.group(),
            label=label,
            start=start,
            end=end,
            redact=label in REDACT_LABELS,
            label_name=PHI_LABELS.get(label, label),
        ))
        covered.add((start, end))

    # Priority order: most specific first
    for pattern, label in [
        (CALLSIGN_REGEX,       "CALLSIGN"),
        (SERVICE_NUMBER_REGEX, "SERVICE_NO"),
        (RANK_NAME_REGEX,      "RANK_NAME"),
        (COORD_REGEX,          "COORD"),
        (FACILITY_REGEX,       "FACILITY"),
        (UNIT_STRENGTH_REGEX,  "UNIT_STRENGTH"),
        (MILITARY_TIME_REGEX,  "MILITARY_TIME"),
        (AREA_REGEX,           "AREA"),
        (BADGE_CONTEXT_REGEX,  "BADGE"),
        (SSN_REGEX,            "SSN"),
        (MRN_REGEX,            "MRN"),
        (PHONE_REGEX,          "PHONE"),
        (EMAIL_REGEX,          "EMAIL"),
        (DOB_REGEX,            "DOB"),
        (BADGE_REGEX,          "BADGE"),
    ]:
        # Special handling for badge context — only redact the number not "badge"
        if pattern is BADGE_CONTEXT_REGEX:
            for m in pattern.finditer(text):
                start, end = m.start(1), m.end(1)
                if not any(s <= start < e or s < end <= e for s, e in covered):
                    entities.append(PHIEntity(
                        text=m.group(1),
                        label="BADGE",
                        start=start,
                        end=end,
                        redact=True,
                        label_name=PHI_LABELS.get("BADGE", "BADGE"),
                    ))
                    covered.add((start, end))
            continue
        
        for m in pattern.finditer(text):
            add(m, label)

    return entities


# ── Tier 2: spaCy on masked text — plain names only ──────────────────────────

def _mask_spans(text: str, entities: list[PHIEntity]) -> str:
    """
    Replace detected spans with same-length placeholder before spaCy.
    spaCy never sees service numbers, callsigns, coords → no misclassification.
    Uses a non-alphabetic character so spaCy doesn't form entities across gaps.
    """
    chars = list(text)
    for e in entities:
        for i in range(e.start, e.end):
            chars[i] = '░'
    return ''.join(chars)


def _spacy_scan(masked_text: str, original_text: str,
                covered: set[tuple[int, int]]) -> list[PHIEntity]:
    """
    Run spaCy NER on masked text.
    Accept PERSON and DOB entities — everything else handled by regex.
    """
    nlp = get_phi_model()
    doc = nlp(masked_text)
    entities = []

    SPACY_ACCEPT = {"PERSON", "DOB"}
    PROWORDS = {
    "roger", "wilco", "over", "out", "wait-out",
    "say", "again", "figures", "sunray", "tiger", "niner", "groundhog", "taccom",
    "rover", "relay", "control", "zero", "main",
    }

    for ent in doc.ents:
        if ent.label_ not in SPACY_ACCEPT:
            continue
        start, end = ent.start_char, ent.end_char
        original_span = original_text[start:end]
        if ent.label_ == "PERSON" and original_span.lower() in LOCATION_NAMES:
            continue
        if ent.label_ == "PERSON" and original_span.lower() in PROWORDS:
            continue
        if any(s <= start < e or s < end <= e for s, e in covered):
            continue
        original_span = original_text[start:end]
        if original_span.count('░') > len(original_span) // 2:
            continue
        if ent.label_ == "PERSON" and len(original_span.strip()) < 4:
            continue
        entities.append(PHIEntity(
            text=original_span,
            label=ent.label_,
            start=start,
            end=end,
            redact=ent.label_ in REDACT_LABELS,
            label_name=PHI_LABELS.get(ent.label_, ent.label_),
        ))

    return entities

def _extend_facility_with_location(text: str, entities: list[PHIEntity]) -> list[PHIEntity]:
    """
    Extend FACILITY entities to include adjacent city/location names.
    e.g. 'Naval Base Karwar' → extend to include 'Karwar'
         'Ambala Airbase' → extend to include 'Ambala'
    """
    result = []
    facility_indices = {i for i, e in enumerate(entities) if e.label == "FACILITY"}

    for i, e in enumerate(entities):
        if e.label != "FACILITY":
            result.append(e)
            continue

        start, end = e.start, e.end

        # Check word AFTER facility (e.g. Naval Base → Karwar)
        remaining = text[end:]
        after_match = re.match(r'^[\s,]+(\w+)', remaining)
        if after_match:
            word = after_match.group(1)
            if word.lower() in LOCATION_NAMES:
                end = end + after_match.end()

        # Check word BEFORE facility (e.g. Ambala → Airbase)
        preceding = text[:start]
        before_match = re.search(r'(\w+)\s*$', preceding)
        if before_match:
            word = before_match.group(1)
            if word.lower() in LOCATION_NAMES:
                start = before_match.start()

        result.append(PHIEntity(
            text=text[start:end],
            label="FACILITY",
            start=start,
            end=end,
            redact=True,
            label_name="Military Facility",
        ))

    return result


# ── Main detect() ─────────────────────────────────────────────────────────────

def detect(text: str) -> DetectionResult:
    """
    Scan text for PHI/PII entities.
    Clean two-tier pipeline: regex first, spaCy on masked text second.
    """
    if not text or not text.strip():
        return DetectionResult(
            original_text=text, entities=[],
            phi_detected=False, redacted_text=text,
            entity_count=0, redacted_count=0,
        )

    # ── Tier 1: Regex ─────────────────────────────────────────────────────
    entities = _regex_scan(text)
    entities = _extend_facility_with_location(text, entities)
    covered  = {(e.start, e.end) for e in entities}

    # ── Tier 2: spaCy on masked text ──────────────────────────────────────
    masked       = _mask_spans(text, entities)
    spacy_ents   = _spacy_scan(masked, text, covered)
    entities     = entities + spacy_ents

    # ── Redact ────────────────────────────────────────────────────────────
    redactable   = [e for e in entities if e.redact]
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
    """Replace PHI entities with typed placeholders, end-to-start."""
    sorted_ents = sorted(entities, key=lambda e: e.start, reverse=True)
    result = text
    for entity in sorted_ents:
        placeholder = f"[{entity.label}]"
        result = result[:entity.start] + placeholder + result[entity.end:]
    return result


# ── Legacy helpers (kept for scan_dict / scan_list compatibility) ─────────────

def scan_dict(data: dict) -> tuple[dict, bool]:
    """Recursively scan a dictionary for PHI in string values."""
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


# ── Novelty check (for Tier 3 LLM escalation) ────────────────────────────────

def novelty_check(text: str, tier12_result: DetectionResult) -> bool:
    """
    Decide whether to escalate to LLM.
    Only escalates if Tier 1+2 likely missed something.
    """
    if len(text.split()) < 3:
        return False

    found_labels = {e.label for e in tier12_result.entities}

    # Rank present but no rank+name detected
    words = set(text.lower().split())
    rank_present = bool(words & MILITARY_RANKS)
    person_found = bool(found_labels & {"PERSON", "RANK_NAME"})
    if rank_present and not person_found:
        return True

    # Badge-like numbers not caught
    badge_matches = BADGE_REGEX.findall(text)
    badge_found   = bool(found_labels & {"BADGE", "SSN", "MRN", "SERVICE_NO"})
    if badge_matches and not badge_found:
        return True

    return False


# ── Tier 3: LLM detection ─────────────────────────────────────────────────────

async def detect_with_llm(text: str) -> DetectionResult:
    """
    Tiered PII detection:
    Tier 1+2: regex + spaCy (fast, <50ms)
    Tier 3:   LLM via Ollama (only if novelty_check passes, ~4.7s)
    Cache:    LLM results cached 1 hour
    """
    tier12_result = detect(text)

    if not novelty_check(text, tier12_result):
        logger.debug(f"Tier 1+2 sufficient | entities={tier12_result.entity_count}")
        return tier12_result

    cached = pii_cache.get(text)
    if cached:
        logger.debug("LLM cache hit")
        return cached

    logger.info("Escalating to LLM (novel pattern detected)")

    prompt = (
        f'You are a PII redaction system for defence communications.\n\n'
        f'Text: "{text}"\n\n'
        f'Identify ALL sensitive personal identifiers. Return ONLY a JSON array:\n'
        f'[{{"text": "exact substring to redact", "label": "LABEL"}}]\n\n'
        f'Detection rules:\n'
        f'- Military rank + name → label: RANK_NAME\n'
        f'- Full name without rank → label: PERSON\n'
        f'- Any ID or badge number → label: BADGE\n'
        f'- Phone numbers → label: PHONE\n'
        f'- Email addresses → label: EMAIL\n'
        f'- SSN (XXX-XX-XXXX) → label: SSN\n'
        f'- Return [] if no PII found\n'
        f'- Return ONLY valid JSON array, no explanation'
    )

    try:
        response = await complete(
            prompt=prompt,
            system="You are a PII detection API. Return only valid JSON.",
            max_tokens=100,
        )
        match = re.search(r'\[.*?\]', response, re.DOTALL)
        if not match:
            return tier12_result

        entities_raw = json.loads(match.group())
        if not entities_raw:
            return tier12_result

        redacted = text
        entities = []
        positioned = []

        for e in entities_raw:
            idx = text.find(e["text"])
            if idx >= 0:
                positioned.append((idx, idx + len(e["text"]), e["text"], e["label"]))

        positioned.sort(key=lambda x: x[0])
        deduped = []
        for item in positioned:
            if deduped and item[0] < deduped[-1][1]:
                if (item[1] - item[0]) > (deduped[-1][1] - deduped[-1][0]):
                    deduped[-1] = item
            else:
                deduped.append(item)

        # Add Tier 1+2 entities not covered by LLM
        llm_covered = {(s, e) for s, e, _, _ in deduped}
        for ent in tier12_result.entities:
            if not ent.redact:
                continue
            if not any(s <= ent.start < e for s, e in llm_covered):
                deduped.append((ent.start, ent.end, ent.text, ent.label))

        deduped.sort(key=lambda x: x[0], reverse=True)
        for start, end, orig_text, label in deduped:
            redacted = redacted[:start] + f"[{label}]" + redacted[end:]
            entities.append(PHIEntity(
                text=orig_text, label=label,
                start=start, end=end,
                redact=True, label_name=label,
            ))

        result = DetectionResult(
            original_text=text,
            entities=entities,
            phi_detected=len(entities) > 0,
            redacted_text=redacted,
            entity_count=len(entities),
            redacted_count=len(entities),
        )

        pii_cache.set(text, result)
        return result

    except Exception as e:
        logger.warning(f"LLM detection failed, using Tier 1+2 result: {e}")
        return tier12_result
