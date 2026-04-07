"""
MCPilot — PHI NER Model
spaCy pipeline for plain name detection only.

Role: Catch plain names (John Smith, Sarah Johnson) that have no
military rank prefix and cannot be detected by regex alone.

All military patterns (callsigns, service numbers, coordinates,
facilities, ranks) are handled by regex in phi_detector.py.
spaCy only needs to catch PERSON entities.
"""
import spacy
from spacy.language import Language
from app.compliance.patterns import DOB_CONTEXT_KEYWORDS
from app.core.logging import get_logger

logger = get_logger(__name__)

_nlp: Language | None = None


def get_phi_model() -> Language:
    """
    Returns the singleton spaCy pipeline.
    Minimal configuration — plain name detection only.
    """
    global _nlp
    if _nlp is not None:
        return _nlp

    logger.info("Loading spaCy PHI model (en_core_web_sm)...")

    nlp = spacy.load("en_core_web_sm")

    # Add DOB context detector AFTER NER
    nlp.add_pipe("dob_context_detector", after="ner")

    _nlp = nlp
    logger.info("PHI model loaded ✓")
    return _nlp


@Language.component("dob_context_detector")
def dob_context_detector(doc):
    """
    Upgrades DATE entities to DOB when near date-of-birth keywords.
    """
    new_ents = []
    for ent in doc.ents:
        if ent.label_ == "DATE":
            context_start  = max(0, ent.start - 5)
            context_tokens = [t.text.lower() for t in doc[context_start:ent.start]]
            context_text   = " ".join(context_tokens)
            if any(kw in context_text for kw in DOB_CONTEXT_KEYWORDS):
                new_ent = doc.char_span(ent.start_char, ent.end_char, label="DOB")
                new_ents.append(new_ent if new_ent else ent)
            else:
                new_ents.append(ent)
        else:
            new_ents.append(ent)
    doc.ents = new_ents
    return doc
