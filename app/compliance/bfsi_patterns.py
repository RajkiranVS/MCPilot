# ══════════════════════════════════════════════════════════════════════════════
# BFSI PII PATTERNS
# Covers Indian financial identity and account data per:
#   - RBI Data Localisation Guidelines
#   - DPDP Act 2023 (Digital Personal Data Protection)
#   - PCI-DSS v4.0
#   - SEBI KYC norms
# ══════════════════════════════════════════════════════════════════════════════

import re

# ── PAN (Permanent Account Number) ───────────────────────────────────────────
# Format: 5 letters + 4 digits + 1 letter (e.g. ABCDE1234F)
PAN_REGEX = re.compile(
    r'\b[A-Z]{5}[0-9]{4}[A-Z]\b'
)

# ── Aadhaar Number ────────────────────────────────────────────────────────────
# 12-digit number, optionally space/hyphen separated in groups of 4
AADHAAR_REGEX = re.compile(
    r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b'
)

# ── Bank Account Number ───────────────────────────────────────────────────────
# Indian bank accounts: 9-18 digits, must have context keyword nearby
# Context-free match risks false positives on any long number
ACCOUNT_NUMBER_REGEX = re.compile(
    r'(?:account|a\/c|acc|acct)[\s#:.-]*(\d{9,18})\b',
    re.IGNORECASE
)

# ── IFSC Code ─────────────────────────────────────────────────────────────────
# Format: 4 letters + 0 + 6 alphanumeric (e.g. SBIN0001234)
IFSC_REGEX = re.compile(
    r'\b[A-Z]{4}0[A-Z0-9]{6}\b'
)

# ── SWIFT / BIC Code ─────────────────────────────────────────────────────────
# Format: 8 or 11 characters (e.g. SBININBB or SBININBBXXX)
SWIFT_REGEX = re.compile(
    r'\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b'
)

# ── Credit / Debit Card Number ───────────────────────────────────────────────
# 13-19 digits, optionally space/hyphen separated in groups of 4
CARD_NUMBER_REGEX = re.compile(
    r'\b(?:\d{4}[\s\-]?){3}\d{4}\b'
)

# ── UPI ID ────────────────────────────────────────────────────────────────────
# Format: username@bankhandle (e.g. user@okicici, 9876543210@upi)
UPI_ID_REGEX = re.compile(
    r'\b[\w.\-]+@(?:okicici|oksbi|okaxis|okhdfcbank|ybl|upi|apl|'
    r'ibl|icici|sbi|hdfc|axis|kotak|paytm|phonepe|gpay)\b',
    re.IGNORECASE
)

# ── GSTIN (GST Identification Number) ────────────────────────────────────────
# Format: 2 digits + 10-char PAN + 1 digit + Z + 1 alphanumeric
GSTIN_REGEX = re.compile(
    r'\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z0-9]\b'
)

# ── CIN (Company Identification Number) ──────────────────────────────────────
# Format: L/U + 5 digits + 2 letters + 4 digits + PTC/LLC/etc + 6 digits
CIN_REGEX = re.compile(
    r'\b[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b'
)

# ── Loan Account Number ───────────────────────────────────────────────────────
LOAN_ACCOUNT_REGEX = re.compile(
    r'(?:loan|home loan|car loan|personal loan|pl|hl|cl)[\s#:.-]*([A-Z0-9]{8,20})\b',
    re.IGNORECASE
)

# ── NACH / Mandate Reference ──────────────────────────────────────────────────
NACH_REGEX = re.compile(
    r'\bNACH[\s\-]?[A-Z0-9]{8,20}\b',
    re.IGNORECASE
)


# ══════════════════════════════════════════════════════════════════════════════
# HEALTHCARE PII PATTERNS
# Covers Indian health identity data per:
#   - DPDP Act 2023
#   - ABDM (Ayushman Bharat Digital Mission) guidelines
#   - Clinical Establishment Act
#   - IRDAI health insurance regulations
# ══════════════════════════════════════════════════════════════════════════════

# ── ABHA Number (Ayushman Bharat Health Account) ─────────────────────────────
# Format: 14-digit number (e.g. 12-3456-7890-1234)
ABHA_REGEX = re.compile(
    r'\b\d{2}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b'
)

# ── ABHA Address ──────────────────────────────────────────────────────────────
# Format: username@abdm (e.g. john.doe@abdm)
ABHA_ADDRESS_REGEX = re.compile(
    r'\b[\w.\-]+@(?:abdm|sbx|nhp)\b',
    re.IGNORECASE
)

# ── Patient MRN / Hospital ID ─────────────────────────────────────────────────
# Contextual — MRN + number, or patient ID + number
PATIENT_MRN_REGEX = re.compile(
    r'(?:mrn|patient[\s\-]?id|patient[\s\-]?no|uhid|'
    r'registration[\s\-]?no|reg[\s\-]?no|opd|ipd)[\s#:.-]*([A-Z0-9]{4,15})\b',
    re.IGNORECASE
)

# ── ICD-10 Diagnosis Code ─────────────────────────────────────────────────────
# Format: Letter + 2 digits + optional dot + 1-4 alphanumeric
# Only flag when in clinical context (near "diagnosis", "dx", "icd")
ICD10_REGEX = re.compile(
    r'(?:diagnosis|dx|icd[\s\-]?10|icd|code)[\s:.-]*([A-Z]\d{2}(?:\.\d{1,4})?)\b',
    re.IGNORECASE
)

# ── Drug / Prescription ───────────────────────────────────────────────────────
# Contextual — prescription/Rx + drug name pattern
PRESCRIPTION_REGEX = re.compile(
    r'(?:rx|prescription|prescribed|medicine|drug|tablet|capsule|syrup)'
    r'[\s:.-]+([A-Za-z]+(?:\s+\d+\s*mg)?)',
    re.IGNORECASE
)

# ── Insurance Policy Number ───────────────────────────────────────────────────
INSURANCE_POLICY_REGEX = re.compile(
    r'(?:policy|policy[\s\-]?no|policy[\s\-]?number|claim[\s\-]?no)'
    r'[\s#:.-]*([A-Z0-9]{6,20})\b',
    re.IGNORECASE
)

# ── TPA / Claim Reference ─────────────────────────────────────────────────────
TPA_CLAIM_REGEX = re.compile(
    r'(?:claim|tpa[\s\-]?ref|preauth|pre[\s\-]?auth|cashless)'
    r'[\s#:.-]*([A-Z0-9]{6,20})\b',
    re.IGNORECASE
)


# ══════════════════════════════════════════════════════════════════════════════
# VERTICAL PATTERN REGISTRIES
# Maps vertical name → list of (regex, label) tuples
# Used by phi_detector.py to run vertical-specific scans
# ══════════════════════════════════════════════════════════════════════════════

BFSI_PATTERNS = [
    (PAN_REGEX,            "PAN"),
    (AADHAAR_REGEX,        "AADHAAR"),
    (ACCOUNT_NUMBER_REGEX, "ACCOUNT_NO"),
    (IFSC_REGEX,           "IFSC"),
    (CARD_NUMBER_REGEX,    "CARD_NO"),
    (UPI_ID_REGEX,         "UPI_ID"),
    (GSTIN_REGEX,          "GSTIN"),
    (CIN_REGEX,            "CIN"),
    (LOAN_ACCOUNT_REGEX,   "LOAN_ACCOUNT"),
    (NACH_REGEX,           "NACH_REF"),
]

HEALTHCARE_PATTERNS = [
    (ABHA_REGEX,            "ABHA_NO"),
    (ABHA_ADDRESS_REGEX,    "ABHA_ADDRESS"),
    (PATIENT_MRN_REGEX,     "PATIENT_MRN"),
    (ICD10_REGEX,           "ICD10_CODE"),
    (PRESCRIPTION_REGEX,    "PRESCRIPTION"),
    (INSURANCE_POLICY_REGEX,"INSURANCE_POLICY"),
    (TPA_CLAIM_REGEX,       "TPA_CLAIM"),
]

# ── Vertical label descriptions ───────────────────────────────────────────────
BFSI_LABEL_DESCRIPTIONS = {
    "PAN":           "Permanent Account Number",
    "AADHAAR":       "Aadhaar Number",
    "ACCOUNT_NO":    "Bank Account Number",
    "IFSC":          "IFSC Code",
    "CARD_NO":       "Credit/Debit Card Number",
    "UPI_ID":        "UPI Payment ID",
    "GSTIN":         "GST Identification Number",
    "CIN":           "Company Identification Number",
    "LOAN_ACCOUNT":  "Loan Account Number",
    "NACH_REF":      "NACH/Mandate Reference",
}

HEALTHCARE_LABEL_DESCRIPTIONS = {
    "ABHA_NO":          "ABHA Health Account Number",
    "ABHA_ADDRESS":     "ABHA Digital Health Address",
    "PATIENT_MRN":      "Patient Medical Record Number",
    "ICD10_CODE":       "ICD-10 Diagnosis Code",
    "PRESCRIPTION":     "Prescription / Drug Reference",
    "INSURANCE_POLICY": "Insurance Policy Number",
    "TPA_CLAIM":        "TPA / Claim Reference Number",
}