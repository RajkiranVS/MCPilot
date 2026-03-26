"""
MCPilot — PHI NER Model
Builds a spaCy pipeline for PHI detection combining:
  1. en_core_web_sm  → pre-trained NER (catches PERSON, DATE, GPE, ORG)
  2. EntityRuler     → rule-based patterns for SSN, MRN, PHONE, EMAIL, ZIP
  3. Custom scorer   → context-aware DOB detection

This runs locally in development and testing.
Week 3: replaced by AWS SageMaker inference endpoint for production.
"""
import spacy
from spacy.language import Language
from spacy.pipeline import EntityRuler
from app.compliance.patterns import REGEX_PATTERNS, DOB_CONTEXT_KEYWORDS
from app.core.logging import get_logger

logger = get_logger(__name__)

_nlp: Language | None = None


def get_phi_model() -> Language:
    """
    Returns the singleton spaCy PHI pipeline.
    Loads and configures on first call, cached after.
    """
    global _nlp
    if _nlp is not None:
        return _nlp

    logger.info("Loading spaCy PHI model (en_core_web_sm)...")

    # Load base English model
    nlp = spacy.load("en_core_web_sm")

    # Add EntityRuler BEFORE the NER component
    # This ensures regex patterns take priority over NER predictions
    ruler = nlp.add_pipe("entity_ruler", before="ner")
    ruler.add_patterns(REGEX_PATTERNS)

    # Add DOB context detector AFTER NER
    nlp.add_pipe("dob_context_detector", after="ner")

    _nlp = nlp
    logger.info("PHI model loaded ✓")
    return _nlp


@Language.component("dob_context_detector")
def dob_context_detector(doc):
    """
    Custom spaCy component that upgrades DATE entities to DOB
    when they appear near date-of-birth context keywords.
    Runs after NER so it can inspect existing entity labels.
    """
    new_ents = []
    for ent in doc.ents:
        if ent.label_ == "DATE":
            # Check surrounding tokens for DOB keywords
            context_start = max(0, ent.start - 5)
            context_tokens = [
                t.text.lower() for t in doc[context_start:ent.start]
            ]
            context_text = " ".join(context_tokens)
            if any(kw in context_text for kw in DOB_CONTEXT_KEYWORDS):
                # Upgrade DATE → DOB
                new_ent = doc.char_span(
                    ent.start_char, ent.end_char, label="DOB"
                )
                new_ents.append(new_ent if new_ent else ent)
            else:
                new_ents.append(ent)
        else:
            new_ents.append(ent)

    doc.ents = new_ents
    return doc