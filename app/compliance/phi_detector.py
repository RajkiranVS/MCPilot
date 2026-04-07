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
import re
import json
from dataclasses import dataclass
from app.compliance.phi_model import get_phi_model
from app.compliance.patterns import (
    REDACT_LABELS, PHI_LABELS, MILITARY_RANKS, BADGE_REGEX,
    COORD_REGEX, UNIT_STRENGTH_REGEX, FACILITY_REGEX, MILITARY_TIME_REGEX,
    CALLSIGN_REGEX, AREA_REGEX, RANK_NAME_REGEX, SERVICE_NUMBER_REGEX,
)
from app.compliance.cache import pii_cache
from app.core.logging import get_logger
from app.core.llm import complete





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


def novelty_check(text: str, spacy_result: DetectionResult) -> bool:
    """
    Decide whether to escalate to LLM.
    Returns True only if text likely contains PII that Tier 1+2 missed.

    Checks:
    1. Military rank words present but no PERSON/RANK_NAME entity found
    2. Badge-like number patterns present but no BADGE entity found
    3. Text is long enough to potentially contain PII (>3 words)
    """
    if len(text.split()) < 3:
        return False  # too short to contain novel PII

    text_lower = text.lower()
    words = set(text_lower.split())
    found_labels = {e.label for e in spacy_result.entities}

    # Check 1 — rank words without person detection
    rank_present = bool(words & MILITARY_RANKS)
    person_found = bool(found_labels & {"PERSON", "RANK_NAME"})
    if rank_present and not person_found:
        logger.debug("Novelty check: rank word found without PERSON entity — escalating to LLM")
        return True

    # Check 2 — badge-like numbers without BADGE/SSN detection
    badge_matches = BADGE_REGEX.findall(text)
    badge_found   = bool(found_labels & {"BADGE", "SSN", "MRN"})
    if badge_matches and not badge_found:
        logger.debug("Novelty check: badge pattern found without entity — escalating to LLM")
        return True

    return False


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

    # ── Tier 1.5: regex sweep for tactical patterns ───────────────────────
    entities = _fix_service_number_misclassification(entities)
    entities = _scan_regex_patterns(text, entities)
    entities = _merge_rank_names(text, entities)
    entities = _remove_callsign_in_facility(entities)

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


def _scan_regex_patterns(text: str, entities: list[PHIEntity]) -> list[PHIEntity]:
    """
    Tier 1.5 — regex sweep for tactical patterns not caught by spaCy NER.
    Covers: GPS/MGRS coordinates, unit strength counts, military facilities.
    Runs after spaCy so it only adds entities not already detected.
    NON_PII labels are excluded from coverage so regex can override them.
    """
    NON_PII_SPACY_LABELS = {
        "CARDINAL", "ORDINAL", "QUANTITY", "TIME",
        "PRODUCT", "GPE", "DATE", "ZIP",
    }
    covered = {
        (e.start, e.end) for e in entities
        if e.label not in NON_PII_SPACY_LABELS
    }
    new_entities = [
        e for e in entities
        if e.label not in NON_PII_SPACY_LABELS
    ]

    for pattern, label in [
        (SERVICE_NUMBER_REGEX, "SERVICE_NO"),
        (RANK_NAME_REGEX,      "RANK_NAME"),
        (COORD_REGEX,          "COORD"),
        (UNIT_STRENGTH_REGEX,  "UNIT_STRENGTH"),
        (FACILITY_REGEX,       "FACILITY"),
        (MILITARY_TIME_REGEX,  "MILITARY_TIME"),
        (CALLSIGN_REGEX,       "CALLSIGN"),
        (AREA_REGEX,           "AREA"),
    ]:
        for m in pattern.finditer(text):
            already = any(
                s <= m.start() < e or s < m.end() <= e
                for s, e in covered
            )
            if not already:
                new_entities.append(PHIEntity(
                    text=m.group(),
                    label=label,
                    start=m.start(),
                    end=m.end(),
                    redact=True,
                    label_name=PHI_LABELS.get(label, label),
                ))
                covered.add((m.start(), m.end()))

    # ── Deduplicate — keep stronger label when regex and spaCy overlap ────
    regex_covered = {
        (e.start, e.end) for e in new_entities
        if e.label in {
            "CALLSIGN", "SERVICE_NO", "RANK_NAME", "COORD",
            "UNIT_STRENGTH", "FACILITY", "MILITARY_TIME", "DOB",
            "AREA", "BADGE",
        }
    }
    final_entities = [
        e for e in new_entities
        if (e.start, e.end) not in regex_covered
        or e.label in {
            "CALLSIGN", "SERVICE_NO", "RANK_NAME", "COORD",
            "UNIT_STRENGTH", "FACILITY", "MILITARY_TIME", "DOB",
            "AREA", "BADGE",
        }
    ]

    return final_entities

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

def _merge_rank_names(text: str, entities: list[PHIEntity]) -> list[PHIEntity]:
    """
    Merge military rank words immediately preceding a PERSON entity
    into a single RANK_NAME entity.
    Also captures middle names left between rank and service number.
    """
    result = []

    for i, e in enumerate(entities):
        if e.label == "PERSON":
            prefix_text  = text[:e.start].rstrip()
            prefix_lower = prefix_text.lower()

            matched_rank = ""
            for rank in sorted(MILITARY_RANKS, key=len, reverse=True):
                if prefix_lower.endswith(rank):
                    matched_rank = rank
                    break

            if matched_rank:
                rank_start = prefix_lower.rfind(matched_rank)
                end = e.end
                # Extend to capture additional name tokens after PERSON entity
                remaining = text[end:]
                extra = re.match(r'^(\s+[A-Z][a-z]+)+', remaining)
                if extra:
                    extension_end = end + len(extra.group())
                    entity_starts = {ent.start for ent in entities if ent != e}
                    if not any(end < s <= extension_end for s in entity_starts):
                        end = extension_end
                full_text = text[rank_start:end]
                result.append(PHIEntity(
                    text=full_text,
                    label="RANK_NAME",
                    start=rank_start,
                    end=end,
                    redact=True,
                    label_name="Military Rank + Name",
                ))
            else:
                result.append(e)
        else:
            result.append(e)

    return result

def _remove_callsign_in_facility(entities: list[PHIEntity]) -> list[PHIEntity]:
    """
    Remove CALLSIGN entities that fall inside OR immediately follow a FACILITY span.
    e.g. 'Forward Operating Base Tango' — Tango is the facility name, not a callsign.
    """
    facility_spans = [
        (e.start, e.end) for e in entities if e.label == "FACILITY"
    ]
    result = []
    for e in entities:
        if e.label == "CALLSIGN":
            # Inside facility span
            inside = any(
                fs <= e.start and e.end <= fe
                for fs, fe in facility_spans
            )
            # Immediately after facility span (within 1 space)
            adjacent = any(
                fe <= e.start <= fe + 1
                for fs, fe in facility_spans
            )
            if inside or adjacent:
                # Convert to FACILITY instead of dropping
                result.append(PHIEntity(
                    text=e.text,
                    label="FACILITY",
                    start=e.start,
                    end=e.end,
                    redact=True,
                    label_name="Military Facility",
                ))
            else:
                result.append(e)
        else:
            result.append(e)
    return result

def _fix_service_number_misclassification(
    entities: list[PHIEntity],
) -> list[PHIEntity]:
    """
    Reclassify PERSON entities whose text matches SERVICE_NUMBER_REGEX.
    spaCy sometimes tags IC-78241H style tokens as PERSON.
    """
    result = []
    for e in entities:
        if e.label == "PERSON" and SERVICE_NUMBER_REGEX.fullmatch(e.text.strip()):
            result.append(PHIEntity(
                text=e.text,
                label="SERVICE_NO",
                start=e.start,
                end=e.end,
                redact=True,
                label_name="Military Service Number",
            ))
        else:
            result.append(e)
    return result

async def detect_with_llm(text: str) -> DetectionResult:
    """
    Tiered PII detection:
    Tier 1+2: spaCy (fast, <30ms)
    Tier 3:   LLM via Ollama (only if novelty_check passes, ~3.5s)
    Cache:    LLM results cached 1 hour
    """

    # ── Tier 1+2: spaCy ───────────────────────────────────────────────────────
    spacy_result = detect(text)

    # ── Novelty check ─────────────────────────────────────────────────────────
    if not novelty_check(text, spacy_result):
        logger.debug(f"PII detection: spaCy sufficient, skipping LLM | entities={spacy_result.entity_count}")
        return spacy_result

    # ── Check cache before calling LLM ────────────────────────────────────────
    cached = pii_cache.get(text)
    if cached:
        logger.debug("PII detection: LLM cache hit")
        return cached

    # ── Tier 3: LLM ───────────────────────────────────────────────────────────
    logger.info("PII detection: escalating to LLM (novel pattern detected)")

    prompt = (
        f'You are a PII redaction system for defence communications.\n\n'
        f'Text: "{text}"\n\n'
        f'Identify ALL sensitive personal identifiers. Return ONLY a JSON array:\n'
        f'[{{"text": "exact substring to redact", "label": "LABEL"}}]\n\n'
        f'Detection rules:\n'
        f'- Military rank + name together as ONE entity → label: RANK_NAME\n'
        f'  Examples: "Major Gaurav", "General Rastogi", "Colonel Singh"\n'
        f'  ALWAYS include the rank word WITH the name as a single entity\n'
        f'- If multiple people appear, identify EACH one separately\n'
        f'- Full name without rank → label: PERSON\n'
        f'- Any ID or badge number in ANY format → label: BADGE\n'
        f'- Phone numbers → label: PHONE\n'
        f'- Email addresses → label: EMAIL\n'
        f'- SSN (XXX-XX-XXXX format only) → label: SSN\n'
        f'- CRITICAL: Never split a rank+name — "Major Aryan" is ONE entity\n'
        f'- CRITICAL: Find ALL people in the text, not just the first one\n'
        f'- Choose ONE label per entity — never combine with pipe or slash\n'
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
            return spacy_result

        entities_raw = json.loads(match.group())
        if not entities_raw:
            return spacy_result

        # ── Use LLM result directly, don't merge with spaCy ──────────────────
        # LLM has full context — its entities are more accurate than spaCy
        # for military rank+name combinations and novel badge formats
        redacted = text
        entities = []
        positioned = []

        for e in entities_raw:
            idx = text.find(e["text"])
            if idx >= 0:
                positioned.append((idx, idx + len(e["text"]), e["text"], e["label"]))

        # Deduplicate overlaps — keep longer entity
        positioned.sort(key=lambda x: x[0])
        deduped = []
        for item in positioned:
            if deduped and item[0] < deduped[-1][1]:
                if (item[1] - item[0]) > (deduped[-1][1] - deduped[-1][0]):
                    deduped[-1] = item
            else:
                deduped.append(item)

        # Also add spaCy entities not covered by LLM
        for spacy_ent in spacy_result.entities:
            if not spacy_ent.redact:
                continue
            covered = any(
                s <= spacy_ent.start < e
                for s, e, _, _ in deduped
            )
            if not covered:
                deduped.append((
                    spacy_ent.start, spacy_ent.end,
                    spacy_ent.text, spacy_ent.label
                ))

        # Sort and redact end-to-start
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
        logger.warning(f"LLM PII detection failed, using spaCy result: {e}")
        return spacy_result
