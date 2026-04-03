"""
MCPilot — PHI Regex Patterns
Multi-token patterns for spaCy EntityRuler.
"""
import re

# ── Military ranks (Indian Armed Forces + common) ─────────────────────────────
MILITARY_RANKS = {
    "general", "major", "colonel", "captain", "lieutenant",
    "brigadier", "wing commander", "squadron leader", "flight lieutenant",
    "sergeant", "corporal", "private", "admiral", "commodore",
    "marshal", "naib subedar", "subedar", "havildar", "sepoy",
    "rear admiral", "vice admiral", "air marshal", "air commodore",
    "group captain", "warrant officer", "petty officer",
}

# ── Badge/ID number pattern (any hyphenated number sequence) ─────────────────
BADGE_REGEX = re.compile(
    r'\b\d{3,6}[-/]\d{2,6}(?:[-/]\d{2,6})?\b'
)

# ── Sector/channel/frequency references ──────────────────────────────────────
SECTOR_REGEX = re.compile(
    r'\b(?:sector|channel|frequency|freq|grid|zone)[-\s]?\d+\w*\b',
    re.IGNORECASE
)

REGEX_PATTERNS = [
    # SSN: 123-45-6789
    {
        "label": "SSN",
        "pattern": [
            {"TEXT": {"REGEX": r"^\d{3}$"}},
            {"TEXT": "-"},
            {"TEXT": {"REGEX": r"^\d{2}$"}},
            {"TEXT": "-"},
            {"TEXT": {"REGEX": r"^\d{4}$"}},
        ],
    },
    # SSN: 123456789
    {
        "label": "SSN",
        "pattern": [
            {"TEXT": {"REGEX": r"^\d{9}$"}},
        ],
    },
    # MRN: MRN1234567
    {
        "label": "MRN",
        "pattern": [
            {"TEXT": {"REGEX": r"^MRN[-:]?\d{6,10}$"}},
        ],
    },
    # MRN: MRN 1234567
    {
        "label": "MRN",
        "pattern": [
            {"TEXT": {"REGEX": r"^MRN$"}},
            {"TEXT": {"REGEX": r"^\d{6,10}$"}},
        ],
    },
    # Phone: 555-123-4567
    {
        "label": "PHONE",
        "pattern": [
            {"TEXT": {"REGEX": r"^\d{3}$"}},
            {"TEXT": "-"},
            {"TEXT": {"REGEX": r"^\d{3}$"}},
            {"TEXT": "-"},
            {"TEXT": {"REGEX": r"^\d{4}$"}},
        ],
    },
    # Phone: (555) 123-4567
    {
        "label": "PHONE",
        "pattern": [
            {"TEXT": "("},
            {"TEXT": {"REGEX": r"^\d{3}$"}},
            {"TEXT": ")"},
            {"TEXT": {"REGEX": r"^\d{3}$"}},
            {"TEXT": "-"},
            {"TEXT": {"REGEX": r"^\d{4}$"}},
        ],
    },
    # Phone: 555.123.4567
    {
        "label": "PHONE",
        "pattern": [
            {"TEXT": {"REGEX": r"^\d{3}$"}},
            {"TEXT": "."},
            {"TEXT": {"REGEX": r"^\d{3}$"}},
            {"TEXT": "."},
            {"TEXT": {"REGEX": r"^\d{4}$"}},
        ],
    },
    # Email
    {
        "label": "EMAIL",
        "pattern": [
            {"TEXT": {"REGEX": r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"}},
        ],
    },
    # ZIP: 12345
    {
        "label": "ZIP",
        "pattern": [
            {"TEXT": {"REGEX": r"^\d{5}$"}},
        ],
    },
    # ZIP: 12345-6789
    {
        "label": "ZIP",
        "pattern": [
            {"TEXT": {"REGEX": r"^\d{5}$"}},
            {"TEXT": "-"},
            {"TEXT": {"REGEX": r"^\d{4}$"}},
        ],
    },
]

DOB_CONTEXT_KEYWORDS = {
    "born", "dob", "birthdate", "birth date",
    "date of birth", "birthday", "b.d.", "b/d"
}

PHI_LABELS = {
    "PERSON":   "Person Name",
    "SSN":      "Social Security Number",
    "MRN":      "Medical Record Number",
    "DOB":      "Date of Birth",
    "PHONE":    "Phone Number",
    "EMAIL":    "Email Address",
    "ZIP":      "ZIP Code",
    "DATE":     "Date (potential DOB)",
    "GPE":      "Location",
}

REDACT_LABELS = {"PERSON", "SSN", "MRN", "DOB", "PHONE", "EMAIL"}