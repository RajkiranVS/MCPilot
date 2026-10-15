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
# Negative lookahead excludes ISO date prefixes (19xx- / 20xx-) so timestamps
# like 2026-04-15 are not mistakenly flagged as badge numbers.
BADGE_REGEX = re.compile(
    r'\b(?!(?:19|20)\d{2}[-/])\d{3,6}[-]\d{2,6}(?:[-]\d{2,6})?\b'
)

# ── Badge with explicit context keyword ───────────────────────────────────────
# Catches "badge 112-334-5567" — prevents phone regex claiming it first
BADGE_CONTEXT_REGEX = re.compile(
    r'\bbadge\s+([\d][\d\-/]{4,})\b',
    re.IGNORECASE
)

# ── GPS / Coordinate patterns (single definition) ────────────────────────────
# Covers: MGRS, Decimal Lat/Long, Degrees/Minutes/Seconds
COORD_REGEX = re.compile(
    r'\b\d{1,2}[A-X]\s+[A-Z]{2}\s+\d{2,10}(?:\s+\d{2,10})?\b|'   # MGRS
    r'\b\d{1,3}°?\s*\d{0,2}\'?\s*\d{0,2}\"?\s*[NS]\s*,?\s*'
    r'\d{1,3}°?\s*\d{0,2}\'?\s*\d{0,2}\"?\s*[EW]\b|'              # DMS (° optional)
    r'\b\d{1,3}\.\d+°?\s*[NS]\s*,?\s*\d{1,3}\.\d+°?\s*[EW]\b',   # Decimal
    re.IGNORECASE
)

# ── Unit strength & Tactical Counts ──────────────────────────────────────────
UNIT_STRENGTH_REGEX = re.compile(
    r'\b\d+\s+(?:\w+\s+)?(?:personnel|soldiers|troops|men|women|officers|jawans|units|'
    r'vehicles|platoons?|companies|company|battalions?|bn|bde|'
    r'commandos?|rangers?|paratroopers?)\b',
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
    "rv", "rendezvous", "ap", "international border",
    "line of control",
    "line of actual control",
    "actual ground position line", "agpl",
    "forward line of own troops", "flot",
    "zero line", "zl", "northern most point", "nmp", "point of actual control", "pac",
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
    r'ALPHA|BRAVO|CHARLIE|DELTA|ECHO|FOXTROT|GOLF|HOTEL|JULIET|'
    r'KILO|LIMA|MIKE|NOVEMBER|OSCAR|PAPA|QUEBEC|ROMEO|SIERRA|TANGO|'
    r'UNIFORM|VICTOR|WHISKEY|XRAY|YANKEE|ZULU|'
    r'SUNRAY|TIGER|NINER|GROUNDHOG|TACCOM|ROVER|RELAY|'
    r'ZERO|MAIN'
    r')(?:\s+\d{1,2}(?:[-/]\d{1,2})?)?\b(?![-\w])',
    re.IGNORECASE
)

# Blocklist — patterns spaCy should never tag as PERSON
NEVER_PERSON = [
    "type-052", "type-054", "type-056", "type-071", "type-075",
    "ssk", "ssn", "ssbn", "ddg", "ffg", "cvn", "lhd",
    "p-8i", "mh-60", "ins", "uss", "hms", "pns",
]

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
    r'\b(?:[01]\d|2[0-3])[0-5]\d\s*(?:hours?|hrs?|zulu|local)\b'
    r'|(?<!\d)(?!(?:19|20)\d{2}\b)(?:[01]\d|2[0-3])[0-5]\d\b(?!\s*[-:T\w\d])',
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
    "CLINICAL_ID":   "Patient / Hospital Identifier",
}

REDACT_LABELS = {
    "PERSON", "SSN", "MRN", "DOB", "PHONE", "EMAIL", "CLINICAL_ID",
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

# ── Clinical document header fields (Indian hospital formats) ─────────────────
# Hospital records print identity in labelled header fields, often in ALL CAPS
# ("Name: MR A B C Age/Sex: 36 Yrs/Male"), which spaCy NER misses. These
# patterns redact the field VALUE (capture group 1) and keep the label.

# Labels that start the next header field on the same line — a value stops there.
_NEXT_FIELD = (
    r'(?:age\s*/\s*sex|age|sex|gender|dob|date|time|visit\s*no|hospital\s*no|uhid|mrn|'
    r'ip\s*no|op\s*no|bed(?:\s*no)?|ward|unit|speciality|specialty|department|dept|'
    r'doctor(?:\s*name)?|consultant|ref(?:\.|erred)?\s*by|address|phone|mobile|contact|'
    r'abha(?:\s*(?:no|number|id))?|aadhaa?r(?:\s*no)?|reg(?:\.|istration)?\s*no|patient\s*id)'
)
_VALUE_END = rf'(?=[ \t]+{_NEXT_FIELD}\.?[ \t]*[:\-]|[ \t]*(?:\r?\n|$)|[ \t]{{2,}}|[ \t]*[,;|])'

CLINICAL_ID_FIELD_REGEX = re.compile(
    r'\b(?:hospital\s*no|uhid|urn|mrn|mrd?\s*no|i\.?p\.?d?\s*no|o\.?p\.?d?\s*no|visit\s*no|'
    r'reg(?:\.|istration)?\s*no|patient\s*id|case\s*no|bill\s*no|policy\s*no|claim\s*no|'
    r'member\s*id|card\s*no|abha(?:\s*(?:no|number|id|address))?|aadhaa?r(?:\s*(?:no|number))?)'
    r'(?![A-Za-z0-9])\.?[ \t]*[:\-#]?[ \t]*'   # label must end here: "MRN1234567" is left to MRN_REGEX
    r'([A-Za-z0-9@][A-Za-z0-9@./\-]*\d[A-Za-z0-9@./\-]*)',
    re.IGNORECASE
)

# Bare "Name:" only counts at the start of a line or a column — not "Drug name:".
NAME_FIELD_REGEX = re.compile(
    r'(?:\b(?:patient(?:\'?s)?\s*name|pt\.?\s*name|name\s+of\s+(?:the\s+)?patient|doctor\s*name|'
    r'consultant(?:\s*name)?|treating\s+doctor|ref(?:\.|erred)?\s*by|'
    r'(?:father|husband|mother|guardian|spouse)(?:\'?s)?\s*name)'
    r'|(?:^|(?<=\t)|(?<=\|)|(?<=  ))name)'
    r'[ \t]*[:\-][ \t]*'
    r'((?:(?:mr|mrs|ms|miss|master|dr|prof|shri|smt|kum|baby|b/o)\.?[ \t]+)?'
    r'[A-Za-z][A-Za-z.\'\-]*(?:[ \t][A-Za-z][A-Za-z.\'\-]*){0,6}?)' + _VALUE_END,
    re.IGNORECASE | re.MULTILINE
)

# Honorific + capitalised name, e.g. a signature block "DR. A B" or "seen by Dr. X".
_NOT_NAME = (r'(?!(?i:mbbs|md|ms|mrcp|frcp|frcs|dnb|dm|mch|dch|dgo|bds|mds|phd|'
             r'specialty|speciality|department|reg)\b)')
HONORIFIC_NAME_REGEX = re.compile(
    r'\b(?:(?i:dr|mr|mrs|prof|shri|smt|kum)\.?|(?i:ms|miss)\.)[ \t]+'
    rf'({_NOT_NAME}[A-Z][A-Za-z\'\-]+(?:[ \t]+{_NOT_NAME}[A-Z][A-Za-z\'\-]+){{0,3}})'
)

# Aadhaar printed in 4-4-4 groups
AADHAAR_REGEX = re.compile(r'\b[2-9]\d{3}[ \-]\d{4}[ \-]\d{4}\b')

# Countries / financial jurisdictions spaCy sometimes tags as PERSON ("Mauritius").
# Never redacted as a person — geography is material to BFSI review.
COUNTRY_NAMES = {
    "india", "mauritius", "singapore", "netherlands", "cyprus", "japan", "united states",
    "usa", "united kingdom", "uk", "uae", "united arab emirates", "dubai", "germany",
    "france", "switzerland", "luxembourg", "ireland", "hong kong", "china", "korea",
    "south korea", "north korea", "iran", "myanmar", "cayman islands", "cayman",
    "british virgin islands", "bvi", "panama", "seychelles", "bermuda", "jersey",
    "guernsey", "isle of man", "bahamas", "canada", "australia", "russia", "saudi arabia",
    "qatar", "oman", "kuwait", "bahrain", "israel", "pakistan", "bangladesh", "sri lanka",
    "nepal", "bhutan", "maldives", "afghanistan", "malaysia", "indonesia", "thailand",
    "vietnam", "philippines", "taiwan", "brazil", "mexico", "south africa", "nigeria",
    "kenya", "italy", "spain", "sweden", "norway", "denmark", "finland", "belgium", "austria",
}

# Clinical vocabulary spaCy sometimes tags as PERSON ("Pulse Rate", "Fall Risk").
# A PERSON span containing any of these words is dropped.
CLINICAL_TERMS = {
    "pulse", "rate", "systolic", "diastolic", "respiration", "respiratory",
    "temperature", "temp", "weight", "height", "pressure", "arterial", "bmi",
    "spo2", "saturation", "scale", "risk", "pain", "fall", "notes", "opd", "ipd",
    "examination", "diagnosis", "impression", "advice", "history", "complaint",
    "complaints", "findings", "investigation", "investigations", "specialty",
    "speciality", "department", "neurology", "cardiology", "orthopaedics",
    "orthopedics", "medicine", "surgery", "record", "outpatient", "inpatient",
    "discharge", "summary", "admission", "ward", "bed", "visit", "hospital",
}
