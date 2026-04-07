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

    nlp = spacy.load("en_core_web_sm")

    # Add EntityRuler BEFORE the NER component
    ruler = nlp.add_pipe("entity_ruler", before="ner")

    # ── Callsign patterns FIRST — highest priority ────────────────────────
    # Must be added before REGEX_PATTERNS to prevent PROWORD/ORG/GPE
    # misclassification overriding callsign detection
    NATO_PHONETIC = [
        "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf",
        "hotel", "india", "juliet", "kilo", "lima", "mike", "november",
        "oscar", "papa", "quebec", "romeo", "sierra", "tango", "uniform",
        "victor", "whiskey", "xray", "yankee", "zulu",
    ]
    STATION_IDS = [
        "sunray", "tiger", "niner", "groundhog", "taccom",
        "rover", "relay", "control", "base", "zero", "main",
    ]
    callsign_patterns = []
    for cs in NATO_PHONETIC + STATION_IDS:
        callsign_patterns.append({"label": "CALLSIGN", "pattern": [
            {"LOWER": cs}
        ]})
        callsign_patterns.append({"label": "CALLSIGN", "pattern": [
            {"LOWER": cs}, {"IS_DIGIT": True}
        ]})
        callsign_patterns.append({"label": "CALLSIGN", "pattern": [
            {"LOWER": cs},
            {"TEXT": {"REGEX": r"^\d{1,2}[-/]\d{1,2}$"}}
        ]})
    ruler.add_patterns(callsign_patterns)

    # ── REGEX_PATTERNS after callsigns ────────────────────────────────────
    ruler.add_patterns(REGEX_PATTERNS)

    # ── Location blocklist ────────────────────────────────────────────────
    LOCATION_BLOCKLIST = [
        "jodhpur", "delhi", "mumbai", "chennai", "kolkata", "bengaluru",
        "hyderabad", "pune", "jaipur", "lucknow", "chandigarh", "pathankot",
        "ambala", "udhampur", "leh", "siachen", "kargil", "srinagar",
        "jammu", "dehradun", "nagpur", "bhopal", "agra", "meerut",
        "secunderabad", "bangalore", "trivandrum", "coimbatore", "vizag",
    ]
    blocklist_patterns = []
    for loc in LOCATION_BLOCKLIST:
        blocklist_patterns.append({"label": "GPE", "pattern": loc})
        blocklist_patterns.append({"label": "GPE", "pattern": loc.title()})
    ruler.add_patterns(blocklist_patterns)

    # ── Unit strength ─────────────────────────────────────────────────────
    ruler.add_patterns([
        {"label": "UNIT_STRENGTH", "pattern": [
            {"LIKE_NUM": True},
            {"LOWER": {"IN": [
                "personnel", "soldiers", "troops", "men", "women",
                "officers", "jawans", "units", "platoon", "company",
                "battalion", "vehicles",
            ]}}
        ]},
    ])

    # ── Facility patterns ─────────────────────────────────────────────────
    ruler.add_patterns([
        {"label": "FACILITY", "pattern": [
            {"IS_TITLE": True},
            {"LOWER": {"IN": [
                "airbase", "cantonment", "cantt", "barracks",
                "garrison", "depot", "arsenal", "armory", "armoury",
                "bunker", "fort", "outpost", "redoubt", "stronghold",
            ]}}
        ]},
        {"label": "FACILITY", "pattern": [
            {"IS_TITLE": True}, {"LOWER": "air"}, {"LOWER": "base"}
        ]},
        {"label": "FACILITY", "pattern": [
            {"IS_TITLE": True}, {"LOWER": "army"}, {"LOWER": "base"}
        ]},
        {"label": "FACILITY", "pattern": [
            {"IS_TITLE": True}, {"LOWER": "naval"}, {"LOWER": "base"}
        ]},
        {"label": "FACILITY", "pattern": [
            {"LOWER": "ammunition"},
            {"LOWER": {"IN": ["point", "depot", "dump"]}},
            {"IS_TITLE": True}
        ]},
        {"label": "FACILITY", "pattern": [
            {"IS_TITLE": True},
            {"LOWER": "ammunition"},
            {"LOWER": {"IN": ["point", "depot", "dump"]}}
        ]},
        {"label": "FACILITY", "pattern": [
            {"LOWER": "forward"},
            {"LOWER": {"IN": ["operating", "base", "position"]}},
            {"IS_TITLE": True}
        ]},
        {"label": "FACILITY", "pattern": [
            {"LOWER": "observation"}, {"LOWER": "post"}, {"IS_TITLE": True}
        ]},
        {"label": "FACILITY", "pattern": [
            {"LOWER": "command"},
            {"LOWER": {"IN": ["post", "centre", "center", "hq"]}},
            {"IS_TITLE": True}
        ]},
        # Forward Operating Base {Callsign/Name} — absorbs trailing name
        {"label": "FACILITY", "pattern": [
            {"LOWER": "forward"},
            {"LOWER": "operating"},
            {"LOWER": "base"},
            {"IS_TITLE": True}
        ]},
    ])

    # ── Single-word JCO rank + name ───────────────────────────────────────
    SINGLE_RANKS = [
        "havildar", "subedar", "sepoy", "jawan",
        "naik", "rifleman", "gunner", "sapper", "signalman",
    ]
    for rank in SINGLE_RANKS:
        ruler.add_patterns([
            {"label": "RANK_NAME", "pattern": [
                {"LOWER": rank}, {"IS_TITLE": True}
            ]},
            {"label": "RANK_NAME", "pattern": [
                {"LOWER": rank}, {"IS_TITLE": True}, {"IS_TITLE": True}
            ]},
        ])

    # ── Two-word rank + name ──────────────────────────────────────────────
    TWO_WORD_RANKS = [
        ("naib",    "subedar"),
        ("lance",   "naik"),
        ("subedar", "major"),
    ]
    for w1, w2 in TWO_WORD_RANKS:
        ruler.add_patterns([
            {"label": "RANK_NAME", "pattern": [
                {"LOWER": w1}, {"LOWER": w2}, {"IS_TITLE": True}
            ]},
            {"label": "RANK_NAME", "pattern": [
                {"LOWER": w1}, {"LOWER": w2},
                {"IS_TITLE": True}, {"IS_TITLE": True}
            ]},
        ])

    # ── Service number (single token: IC-78241H) ──────────────────────────
    ruler.add_patterns([
        {"label": "SERVICE_NO", "pattern": [
            {"TEXT": {"REGEX": r"^(?:IC|SS|RC|SL|MS|V|TA|NR)-?\d{5,6}[A-Z]$"}}
        ]},
    ])

    # ── DOB patterns ──────────────────────────────────────────────────────
    ruler.add_patterns([
        {"label": "DOB", "pattern": [
            {"LOWER": {"IN": ["dob", "d.o.b", "b.d", "birthdate", "birth"]}},
            {"TEXT": {"IN": [":", "-"]}},
            {"TEXT": {"REGEX": r"^\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}$"}}
        ]},
        {"label": "DOB", "pattern": [
            {"LOWER": {"IN": ["dob", "d.o.b", "birthdate"]}},
            {"TEXT": {"REGEX": r"^\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}$"}}
        ]},
        {"label": "DOB", "pattern": [
            {"LOWER": {"IN": ["born", "birthday", "date", "b/d"]}},
            {"LOWER": {"IN": ["of", ":"]}},
            {"LOWER": "birth", "OP": "?"},
            {"TEXT": {"REGEX": r"^\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}$"}}
        ]},
    ])

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
