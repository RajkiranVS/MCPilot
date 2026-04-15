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


@Language.component("military_blocklist")
def military_blocklist(doc):
    """
    Removes PERSON tags from military/technical terms that spaCy
    incorrectly identifies as names.
    """
    NEVER_PERSON = {
        # Vessel type designators
        "type-052", "type-052d", "type-054", "type-054a", "type-056",
        "type-071", "type-075", "type-093", "type-094",
        # Submarine/ship class codes
        "ssk", "ssn", "ssbn", "ssbn-", "ddg", "ffg", "cvn", "lhd", "lpd",
        # Aircraft designators
        "p-8i", "p-8", "mh-60r", "mh-60", "uh-60", "ah-64",
        # Ship prefixes and names that aren't people
        "ins", "uss", "hms", "pns", "pla",
        # Ship names and military unit names
        "ins visakhapatnam", "ins vikrant", "ins kolkata",
        "ins shivalik", "ins arihant", "ins trishul", "ins talwar",
        "ins delhi", "ins mumbai", "ins chennai", "ins mysore",
        # Military unit terms
        "vlsm", "sloc", "emcon", "sosus", "sigint", "humint",
        "satint", "imint", "masint", "osint",
        # Common false positives
        "control", "sierra", "oscar", "romeo", "victor",
    }

    # Token prefixes that always indicate a vessel name, not a person name.
    # If any of these appear immediately before the entity, suppress PERSON.
    VESSEL_PREFIXES = {
        "ins", "uss", "hms", "pns", "hmcs", "js", "rss", "ots",
        "mns", "bns", "rims", "sns", "lns", "cgs", "icgs",
        "plan",  # People's Liberation Army Navy vessel
        "vessel", "ship", "warship", "frigate", "destroyer",
        "corvette", "submarine", "carrier", "tanker", "trawler",
        "tugboat", "patrol", "boat", "craft",
    }

    new_ents = []
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            text_lower = ent.text.lower()

            # 1. Static blocklist match (exact, prefix, or suffix)
            if any(
                text_lower == blocked
                or text_lower.startswith(blocked)
                # spaCy may tag the suffix of a compound name (e.g. "Visakhapatnam"
                # from "INS Visakhapatnam") — catch it via the blocked entry's suffix
                or (len(text_lower) > 4 and blocked.endswith(text_lower))
                for blocked in NEVER_PERSON
            ):
                continue  # Drop this entity

            # 2. Context-based check: look at the two tokens before the entity.
            # If any preceding token is a vessel prefix, this is a ship name.
            context_start = max(0, ent.start - 2)
            preceding = [t.text.lower() for t in doc[context_start:ent.start]]
            if any(tok in VESSEL_PREFIXES for tok in preceding):
                continue  # Drop — it's a vessel name following a ship prefix

        new_ents.append(ent)

    doc.ents = new_ents
    return doc

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

    # Add post-NER filters: blocklist first, then DOB upgrader
    nlp.add_pipe("military_blocklist", after="ner")
    nlp.add_pipe("dob_context_detector", after="military_blocklist")

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
