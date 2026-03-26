"""
MCPilot — PHI Regex Patterns
Multi-token patterns for spaCy EntityRuler.
"""

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