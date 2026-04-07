"""
MCPilot — PHI & Tactical Regex Patterns
Comprehensive patterns for military-grade PII/CUI redaction.
"""
import re

# In patterns.py
# In patterns.py
LOCATION_NAMES = {
    "karwar", "ambala", "pathankot", "jodhpur", "delhi", "mumbai",
    "chennai", "kolkata", "bengaluru", "hyderabad", "pune", "jaipur",
    "lucknow", "chandigarh", "udhampur", "leh", "siachen", "kargil",
    "srinagar", "jammu", "dehradun", "nagpur", "bhopal", "agra",
    "meerut", "secunderabad", "bangalore", "trivandrum", "coimbatore",
    "vizag", "shimla", "portblair", "mussoorie",
}

# ── Military Ranks (Indian Armed Forces + Global) ─────────────────────────────
MILITARY_RANKS = {
    "general", "major general", "lieutenant general", "major", "colonel", "lt col",
    "captain", "lieutenant", "lt", "brigadier", "wing commander", "squadron leader",
    "flight lieutenant", "sergeant", "corporal", "private", "admiral", "commodore",
    "marshal", "naib subedar", "subedar", "havildar", "sepoy", "jawan",
    "rear admiral", "vice admiral", "air marshal", "air commodore",
    "group captain", "warrant officer", "petty officer", "nco", "jco",
}

# ── Indian Military Service Numbers (IC, SS, etc.) ────────────────────────────
SERVICE_NUMBER_REGEX = re.compile(
    r'\b(?:IC|SS|RC|SL|MS|V|TA|NR)[- ]?\d{5,6}[A-Z]\b',
    re.IGNORECASE
)

# ── Badge/ID number pattern ───────────────────────────────────────────────────
BADGE_REGEX = re.compile(
    r'\b\d{3,6}[-/]\d{2,6}(?:[-/]\d{2,6})?\b'
)

# ── GPS / Coordinate patterns (single definition) ────────────────────────────
# Covers: MGRS, Decimal Lat/Long, Degrees/Minutes/Seconds
COORD_REGEX = re.compile(
    r'\b\d{1,2}[A-X]\s+[A-Z]{2}\s+\d{2,10}(?:\s+\d{2,10})?\b|'   # MGRS (with optional easting)
    r'\b\d{1,3}\.\d+°?\s*[NS]\s*,?\s*\d{1,3}\.\d+°?\s*[EW]\b|'    # Decimal Lat/Long
    r'\b\d{1,3}°\s*\d{0,2}\'?\s*\d{0,2}\"?\s*[NS]\s*,?\s*'
    r'\d{1,3}°\s*\d{0,2}\'?\s*\d{0,2}\"?\s*[EW]\b',               # DMS
    re.IGNORECASE
)

# ── Unit strength & Tactical Counts ──────────────────────────────────────────
UNIT_STRENGTH_REGEX = re.compile(
    r'\b\d+\s*(?:personnel|soldiers|troops|men|women|officers|jawans|units|'
    r'vehicles|platoon|company|battalion|bn|bde)\b',
    re.IGNORECASE
)

# ── Military Facilities ───────────────────────────────────────────────────────
FACILITY_KEYWORDS = {
    "airbase", "air base", "air force station", "afs", "army base", "naval base",
    "cantonment", "cantt", "military station", "forward operating base", "fob",
    "command post", "command centre", "command center",
    "brigade hq", "division hq", "corps hq",
    "armory", "armoury", "depot", "barracks", "garrison",
    "border post", "bop", "lac", "loc", "ib",
    "check post", "vcp", "ammunition point", "ammunition depot",
    "observation post", "supply depot", "forward base", "forward position",
    "rv", "rendezvous", "ap",
}
FACILITY_REGEX = re.compile(
    r'\b(?:' + '|'.join(
        re.escape(f) for f in sorted(FACILITY_KEYWORDS, key=len, reverse=True)
    ) + r')\b',
    re.IGNORECASE
)

# ── Sector / Area references ──────────────────────────────────────────────────
SECTOR_REGEX = re.compile(
    r'\b(?:sector|channel|frequency|freq|grid|zone|net|radio)[-\s]?\d+\w*\b',
    re.IGNORECASE
)
AREA_REGEX = re.compile(
    r'\b(?:sector|zone|grid)\s*\d+\b',
    re.IGNORECASE
)

# ── Military Callsigns ────────────────────────────────────────────────────────
CALLSIGN_REGEX = re.compile(
    r'\b(?:'
    r'ALPHA|BRAVO|CHARLIE|DELTA|ECHO|FOXTROT|GOLF|HOTEL|INDIA|JULIET|'
    r'KILO|LIMA|MIKE|NOVEMBER|OSCAR|PAPA|QUEBEC|ROMEO|SIERRA|TANGO|'
    r'UNIFORM|VICTOR|WHISKEY|XRAY|YANKEE|ZULU|'
    r'SUNRAY|TIGER|NINER|GROUNDHOG|TACCOM|ROVER|RELAY|'
    r'CONTROL|ZERO|MAIN'
    r')(?:\s+\d{1,2}(?:[-/]\d{1,2})?)?\b',
    re.IGNORECASE
)

# ── Rank + Name regex fallback ────────────────────────────────────────────────
RANK_NAME_REGEX = re.compile(
    r'\b(?:' +
    '|'.join(
        ''.join(
            f'[{c.upper()}{c.lower()}]' if c.isalpha() else r'\s+'
            for c in r
        )
        for r in sorted(MILITARY_RANKS, key=len, reverse=True)
    ) +
    r')(?:\s+[A-Z][a-z]{1,}){1,3}\b'
)

# ── Military Time (24hr format) ───────────────────────────────────────────────
MILITARY_TIME_REGEX = re.compile(
    r'\b(?:[01]\d|2[0-3])[0-5]\d\s*(?:hours?|hrs?|zulu|local)?\b',
    re.IGNORECASE
)

# ── Proword regex (for reference only — not used for redaction) ───────────────
PROWORD_REGEX = re.compile(
    r'\b(?:tiger|over|out|roger|wilco|say again|wait-out|figures|h-hour|d-day)\b',
    re.IGNORECASE
)

# ── spaCy EntityRuler patterns ────────────────────────────────────────────────
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
        "pattern": [{"TEXT": {"REGEX": r"^\d{9}$"}}],
    },
    # MRN: MRN1234567
    {
        "label": "MRN",
        "pattern": [{"TEXT": {"REGEX": r"^MRN[-:]?\d{6,10}$"}}],
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
        "pattern": [{"TEXT": {"REGEX": r"^\d{5}$"}}],
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
    # Proword blocklist — prevent ROGER/WILCO being classified as PERSON
    {"label": "PROWORD", "pattern": [{"LOWER": {"IN": [
        "roger", "wilco", "over", "out", "wait-out", "standby",
        "say", "again", "figures",
    ]}}]},
]

DOB_CONTEXT_KEYWORDS = {
    "born", "dob", "birthdate", "birth date",
    "date of birth", "birthday", "b.d.", "b/d",
}

PHI_LABELS = {
    "PERSON":        "Person Name",
    "SERVICE_NO":    "Military Service Number",
    "SSN":           "Social Security Number",
    "MRN":           "Medical Record Number",
    "DOB":           "Date of Birth",
    "PHONE":         "Phone Number",
    "EMAIL":         "Email Address",
    "ZIP":           "ZIP Code",
    "DATE":          "Date (potential DOB)",
    "GPE":           "Location",
    "COORD":         "GPS / MGRS Coordinate",
    "UNIT_STRENGTH": "Unit Strength / Troop Count",
    "FACILITY":      "Military Facility",
    "BADGE":         "Badge / ID Number",
    "RANK_NAME":     "Military Rank + Name",
    "MILITARY_TIME": "Military Time / ETA",
    "CALLSIGN":      "Military Callsign",
    "AREA":          "Sector / Grid Area",
    "GRID":          "MGRS Grid Reference",
}

REDACT_LABELS = {
    "PERSON", "SSN", "MRN", "DOB", "PHONE", "EMAIL",
    "SERVICE_NO", "GRID", "COORD",
    "UNIT_STRENGTH", "FACILITY",
    "BADGE", "RANK_NAME",
    "MILITARY_TIME", "CALLSIGN", "AREA",
}

# ── Standalone regex patterns (previously EntityRuler only) ──────────────────
# These are now used by the Tier 1 regex scanner in phi_detector.py

SSN_REGEX = re.compile(
    r'\b\d{3}-\d{2}-\d{4}\b'
)

PHONE_REGEX = re.compile(
    r'\b(?:\+91[\s-]?)?\d{10}\b|'           # Indian mobile: +91 9876543210
    r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b|'     # US: 555-123-4567
    r'\(\d{3}\)\s*\d{3}[-.\s]\d{4}\b'       # (555) 123-4567
)

EMAIL_REGEX = re.compile(
    r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b'
)

MRN_REGEX = re.compile(
    r'\bMRN[-:]?\d{6,10}\b|\bMRN\s+\d{6,10}\b',
    re.IGNORECASE
)

DOB_REGEX = re.compile(
    r'\b(?:dob|d\.o\.b|birthdate|born|birthday)[:\s\-]+\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b',
    re.IGNORECASE
)
