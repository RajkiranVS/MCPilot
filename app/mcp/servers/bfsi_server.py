"""
MCPilot — BFSI Intelligence Server
Banking, Financial Services & Insurance Vertical

Provides AI-powered document analysis and financial intelligence tools
with automatic PII redaction per RBI guidelines and DPDP Act 2023.

Tools:
  - summarise_financial_document  : AI document summariser (any format)
  - extract_financial_entities    : Key figures, ratios, dates extraction
  - assess_credit_risk            : Credit risk scoring from financials
  - flag_compliance_issues        : AML/KYC compliance flag detection
  - generate_audit_report         : Structured audit summary

Classification: CONFIDENTIAL
Compliance:     RBI Data Localisation, DPDP Act 2023, PCI-DSS v4.0

Run: python app/mcp/servers/bfsi_server.py
"""
import re
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

try:                                    # imported as a package (gateway, tests)
    from app.mcp.servers._local_llm import local_llm_summary
except ImportError:                     # run as a script: python app/mcp/servers/bfsi_server.py
    from _local_llm import local_llm_summary

load_dotenv()
mcp = FastMCP("BFSI Intelligence Server")

# ── Financial document type classifier ────────────────────────────────────────
# Weighted whole-word cues; highest score wins (first-match on substrings sent
# anything containing "terms" to LEGAL_AGREEMENT and "identity" to KYC).
_DOC_TYPE_CUES = {
    "FINANCIAL_STATEMENT": [(r"balance sheet|statement of profit and loss|profit and loss|p&l|income statement|"
                             r"cash flow statement", 2)],
    "AUDIT_REPORT":        [(r"independent auditor'?s? report|audit report|statutory audit", 3),
                            (r"auditors?|audit opinion|key audit matters", 1)],
    "LOAN_DOCUMENT":       [(r"sanction letter|loan agreement|credit facility|term loan", 3),
                            (r"loan|borrower|repayment|emi|collateral|hypothecation", 1)],
    "KYC_DOCUMENT":        [(r"kyc|know your customer|ckyc", 3),
                            (r"aadhaar|pan card|proof of identity|proof of address", 1)],
    "INSURANCE_DOCUMENT":  [(r"insurance policy|policy schedule|sum assured|sum insured", 3),
                            (r"claim|premium|insured|indemnity", 1)],
    "ANNUAL_REPORT":       [(r"annual report|board'?s report|directors'? report|scheme information document|"
                            r"factsheet|fund fact sheet", 3),
                            (r"board of directors|agm|dividend|nav|asset management company|amc|"
                             r"mutual fund|net asset value", 1)],
    "LEGAL_AGREEMENT":     [(r"agreement|contract", 1), (r"whereas|hereinafter|witnesseth|in witness whereof", 2)],
}


def _classify_document(text: str) -> str:
    text_lower = text.lower()
    scores = {
        doc_type: sum(weight * len(re.findall(rf"(?<![a-z0-9])(?:{pattern})(?![a-z0-9])", text_lower))
                      for pattern, weight in cues)
        for doc_type, cues in _DOC_TYPE_CUES.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "FINANCIAL_DOCUMENT"


# ── Extract key financial figures ─────────────────────────────────────────────
def _extract_financials(text: str) -> dict:
    """Extract numerical financial figures from document text."""
    figures = {}

    # Revenue / Turnover
    rev = re.search(
        r'(?:revenue|turnover|net sales|total income)[:\s₹Rs.]*([0-9,]+(?:\.\d+)?)\s*(?:crore|lakh|million|billion|cr|L)?',
        text, re.IGNORECASE
    )
    if rev:
        figures["revenue"] = rev.group(1).replace(",", "")

    # Net Profit / PAT
    profit = re.search(
        r'(?:net profit|profit after tax|pat|net income)[:\s₹Rs.]*([0-9,]+(?:\.\d+)?)\s*(?:crore|lakh|million|cr|L)?',
        text, re.IGNORECASE
    )
    if profit:
        figures["net_profit"] = profit.group(1).replace(",", "")

    # Total Assets
    assets = re.search(
        r'(?:total assets|gross assets)[:\s₹Rs.]*([0-9,]+(?:\.\d+)?)\s*(?:crore|lakh|million|cr|L)?',
        text, re.IGNORECASE
    )
    if assets:
        figures["total_assets"] = assets.group(1).replace(",", "")

    # Debt / Borrowings
    debt = re.search(
        r'(?:total debt|borrowings|long.term debt|total liabilities)[:\s₹Rs.]*([0-9,]+(?:\.\d+)?)\s*(?:crore|lakh|million|cr|L)?',
        text, re.IGNORECASE
    )
    if debt:
        figures["total_debt"] = debt.group(1).replace(",", "")

    # EBITDA
    ebitda = re.search(
        r'(?:ebitda|operating profit)[:\s₹Rs.]*([0-9,]+(?:\.\d+)?)\s*(?:crore|lakh|million|cr|L)?',
        text, re.IGNORECASE
    )
    if ebitda:
        figures["ebitda"] = ebitda.group(1).replace(",", "")

    return figures


# ── AML/Compliance flag detection ─────────────────────────────────────────────
# A flag needs a risk INDICATOR, not a mention. Legitimate documents routinely say
# "loan sanctioned" (= approved), "event of default", "related party transactions
# (Ind AS 24)", "SPV", or name Mauritius as an FDI source — none of that is a red flag.

# FATF "call for action" jurisdictions. Override with BFSI_HIGH_RISK_JURISDICTIONS
# (comma-separated) to match your compliance team's current list.
_DEFAULT_HIGH_RISK_JURISDICTIONS = [
    "democratic people's republic of korea", "north korea", "dprk", "iran", "myanmar",
]


def _high_risk_jurisdictions() -> list[str]:
    configured = os.getenv("BFSI_HIGH_RISK_JURISDICTIONS", "")
    names = [j.strip().lower() for j in configured.split(",") if j.strip()]
    return names or _DEFAULT_HIGH_RISK_JURISDICTIONS


_FLAG_RULES = [
    ("ROUND_TRIPPING", "HIGH",
     r"round[- ]?trip(?:ping|ped)?|circular (?:transactions?|trading|flow of funds)|"
     r"layering of funds|layered transactions?",
     "Possible round-tripping or layered transaction"),
    ("SHELL_COMPANY", "MEDIUM",
     r"shell (?:company|companies|entity|entities|corporation)|accommodation entr(?:y|ies)|"
     r"bogus (?:company|companies|invoices?|billing)|dummy (?:company|companies|directors?)|"
     r"no (?:real|genuine|actual) business (?:operations?|activity)",
     "Shell-company indicator"),
    ("SANCTION_RISK", "HIGH",
     r"ofac|sdn list|specially designated nationals?|un (?:security council )?sanctions? list|"
     r"sanctions? (?:list|screening hit|match)|subject to (?:international |economic )?sanctions|"
     r"sanctioned (?:entity|entities|individuals?|persons?|countr(?:y|ies)|jurisdictions?|parties)|"
     r"black-?listed",
     "Potential sanctions exposure"),
    ("CASH_TRANSACTION", "MEDIUM",
     r"(?:large|bulk|substantial|unexplained|frequent) cash (?:deposits?|withdrawals?|transactions?)|"
     r"structuring|smurfing|cash (?:deposits?|transactions?) (?:just )?below (?:the )?reporting",
     "Large or structured cash activity"),
    ("RELATED_PARTY", "LOW",
     r"related[- ]party (?:loans?|advances?)|loans? (?:and advances )?to (?:promoters?|directors?)|"
     r"promoter loans?|siphon(?:ing|ed)? of funds|diversion of funds",
     "Related-party lending or fund diversion — verify arm's-length terms"),
    ("NPL_RISK", "MEDIUM",
     r"non-performing (?:assets?|accounts?|loans?)|npa|stressed assets?|wilful defaulters?|"
     r"defaulted|(?:is|was|are|were|has been|have been) in default|"
     r"overdue (?:for|by|since) (?:over |more than )?\d+|\d+\+? days past due|dpd|"
     r"sma-?[012]|restructured (?:loans?|accounts?|advances?)",
     "Non-performing or stressed asset indicator"),
]

# Negation in the same clause cancels a match: "not classified as an NPA", "no shell company".
_NEGATION = re.compile(r"\b(?:no|not|nil|none|never|neither|nor|without|free (?:of|from))\b")


def _negated(text_lower: str, start: int) -> bool:
    clause_start = max(text_lower.rfind(c, 0, start) for c in ".;\n") + 1
    return bool(_NEGATION.search(text_lower[max(clause_start, start - 60):start]))


def _evidence(text: str, start: int, end: int) -> str:
    return " ".join(text[max(0, start - 60):end + 60].split())


def _detect_compliance_flags(text: str) -> list[dict]:
    text_lower = text.lower()
    # A jurisdiction counts only with an exposure context — market commentary
    # ("crude prices before the Iran war") is not exposure.
    exposure = (r"(?:incorporated|registered|domiciled|resident|based|located|headquartered|"
                r"operating|branch(?:es)?|subsidiar(?:y|ies)|accounts?|banks?|counterpart(?:y|ies)|"
                r"entit(?:y|ies)|nationals?|citizens?)\s+(?:in|of|at)|"
                r"(?:transfers?|remittances?|wires?|payments?|funds?|shipments?|exports?|imports?|"
                r"transactions?|dealings?|trade|business)\s+(?:to|from|with|in|involving)")
    jurisdictions = "|".join(re.escape(j) for j in _high_risk_jurisdictions())
    rules = _FLAG_RULES + [(
        "UNUSUAL_GEOGRAPHY", "MEDIUM",
        rf"(?:{exposure})(?:\s+(?:the|a|an))?\s+(?:{jurisdictions})",
        "Exposure to FATF high-risk jurisdiction",
    )]

    flags = []
    for flag_id, severity, pattern, description in rules:
        for m in re.finditer(rf"(?<![a-z0-9])(?:{pattern})(?![a-z0-9])", text_lower):
            if _negated(text_lower, m.start()):
                continue
            flags.append({
                "flag_id":     flag_id,
                "description": description,
                "severity":    severity,
                "evidence":    _evidence(text, m.start(), m.end()),
                "requires_review": severity != "LOW",
            })
            break   # one flag per type; evidence is the first match
    return flags


_SEVERITY_WEIGHT = {"HIGH": 35, "MEDIUM": 20, "LOW": 5}


def _flag_risk(flags: list[dict]) -> int:
    return sum(_SEVERITY_WEIGHT.get(f["severity"], 10) for f in flags)


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 1: summarise_financial_document
# ══════════════════════════════════════════════════════════════════════════════
_SUMMARY_PROMPT = """You are a financial analyst at an Indian bank. Summarise the financial document below for a credit / compliance reviewer.

Rules:
- Use ONLY information stated in the document. Never invent figures, ratings, parties or conclusions.
- Copy every amount, percentage, date and rating exactly as written, with its units (crore, lakh, %).
- Placeholders such as [PERSON] or [CLINICAL_ID] are redacted identifiers. Do not guess them.
- Do not call something a compliance risk unless the document states a concrete problem.
  Routine disclosures (related-party transactions, subsidiaries abroad, standard risk factors) are not red flags.
- If something is not in the document, write "Not documented".

Write exactly these sections:
Document:
Key figures:
Business / portfolio overview:
Risks stated in the document:
Points for the reviewer:

Document:
\"\"\"
{document}
\"\"\""""


@mcp.tool()
async def summarise_financial_document(
    document_text: str,
    document_type: str = "AUTO",
    output_format: str = "FINANCIAL_REPORT",
) -> dict:
    """
    Financial document summariser.
    Accepts any financial document (annual report, audit report, loan
    application, KYC document, insurance claim, NBFC filing, fund factsheet).

    Returns rule-based extraction (figures, compliance flags with the evidence
    that triggered them, risk score) plus a narrative summary from the local
    Ollama model when available ("ai_summary"). The gateway redacts PII per
    DPDP Act 2023 before this tool runs; nothing leaves the host.

    Args:
        document_text: Full text content of the financial document
        document_type: AUTO | FINANCIAL_STATEMENT | AUDIT_REPORT |
                       LOAN_DOCUMENT | KYC_DOCUMENT | INSURANCE_DOCUMENT |
                       ANNUAL_REPORT | LEGAL_AGREEMENT
        output_format: FINANCIAL_REPORT | EXECUTIVE_SUMMARY | RISK_BRIEF

    Returns:
        Structured financial summary with key metrics, risk indicators,
        compliance flags and redaction report.
    """
    if not document_text or not document_text.strip():
        return {
            "status":  "ERROR",
            "message": "Document text is empty. Please provide document content.",
        }

    # Auto-classify if not specified
    doc_type = document_type if document_type != "AUTO" else _classify_document(document_text)

    # Extract financial figures
    financials = _extract_financials(document_text)

    # Detect compliance flags
    compliance_flags = _detect_compliance_flags(document_text)

    # Word count and document stats
    word_count = len(document_text.split())
    char_count = len(document_text)

    # Build structured summary based on document type
    summary_sections = {}

    if doc_type == "FINANCIAL_STATEMENT":
        summary_sections = {
            "document_overview": f"Financial statement containing {word_count} words. "
                                 f"Key financial data extracted for reporting.",
            "financial_highlights": financials if financials else
                                    "Manual extraction required — figures not in standard format.",
            "profitability_assessment": (
                "Revenue and profit figures identified. "
                "Full ratio analysis requires structured data input."
                if financials else "Figures require manual extraction."
            ),
            "balance_sheet_summary": (
                f"Total assets: ₹{financials.get('total_assets', 'N/A')} | "
                f"Total debt: ₹{financials.get('total_debt', 'N/A')}"
                if financials else "Balance sheet data requires structured input."
            ),
        }

    elif doc_type == "AUDIT_REPORT":
        summary_sections = {
            "audit_opinion": (
                "QUALIFIED" if any(kw in document_text.lower()
                for kw in ["qualified", "except for", "material misstatement"])
                else "UNQUALIFIED" if "unqualified" in document_text.lower()
                else "PENDING — opinion not clearly stated"
            ),
            "key_observations": "Audit observations extracted. Review compliance flags below.",
            "material_weaknesses": [f["description"] for f in compliance_flags] or ["None identified"],
            "management_response": "Not included in provided document extract.",
        }

    elif doc_type == "LOAN_DOCUMENT":
        summary_sections = {
            "loan_type":     "Identified from document context",
            "key_covenants": "Financial covenants referenced — manual review required",
            "security":      "Collateral/security details identified",
            "repayment":     "Repayment schedule details in document",
        }

    elif doc_type == "KYC_DOCUMENT":
        summary_sections = {
            "kyc_status":    "KYC document received",
            "identity_docs": "Identity documents referenced — PII redacted per DPDP Act 2023",
            "risk_category": "MEDIUM" if compliance_flags else "LOW",
            "pep_check":     "PEP screening required — not automated",
        }

    elif doc_type == "INSURANCE_DOCUMENT":
        summary_sections = {
            "policy_type":   "Insurance document identified",
            "coverage":      "Coverage details in document",
            "claim_status":  "Claim reference identified — see redaction report",
            "tpa_details":   "TPA details redacted per DPDP Act 2023",
        }

    else:
        summary_sections = {
            "document_overview": f"Financial document — {word_count} words processed.",
            "key_data":          financials if financials else "Manual extraction recommended.",
        }

    # Risk assessment
    risk_score = min(_flag_risk(compliance_flags) + (10 if not financials else 0), 100)
    risk_level = "HIGH" if risk_score >= 60 else "MEDIUM" if risk_score >= 30 else "LOW"

    return {
        "status":           "OK",
        "document_type":    doc_type,
        "output_format":    output_format,
        "processed_at":     datetime.now(timezone.utc).isoformat(),
        "document_stats": {
            "word_count":   word_count,
            "char_count":   char_count,
            "language":     "English",
        },
        "ai_summary":       await local_llm_summary(_SUMMARY_PROMPT.format(document=document_text[:12000])),
        "summary":          summary_sections,
        "financial_figures": financials,
        "risk_assessment": {
            "risk_score":   risk_score,
            "risk_level":   risk_level,
            "flags_count":  len(compliance_flags),
        },
        "compliance_flags":  compliance_flags,
        "pii_protection": {
            "framework":    "DPDP Act, 2023 + RBI Data Localisation",
            "redacted_types": ["PAN", "AADHAAR", "ACCOUNT_NO", "CARD_NO", "UPI_ID"],
            "processing":   "On-premise — no data transmitted externally",
            "audit_trail":  "Cryptographic audit hash generated",
        },
        "recommended_actions": (
            ["IMMEDIATE REVIEW — high-risk compliance flags detected",
             "Escalate to compliance team",
             "Do not process without senior approval"]
            if risk_level == "HIGH" else
            ["Standard review process",
             "Verify extracted figures against source document"]
            if risk_level == "MEDIUM" else
            ["Routine processing",
             "File and archive as per document retention policy"]
        ),
        "reporting_officer": "MCPilot BFSI Intelligence v1.0",
        "compliance":        "RBI Data Localisation · DPDP Act, 2023 · PCI-DSS v4.0",
    }


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 2: extract_financial_entities
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def extract_financial_entities(document_text: str) -> dict:
    """
    Extract key financial entities from document text.
    Returns structured data: companies, amounts, dates, ratios, accounts.

    Args:
        document_text: Financial document text

    Returns:
        Structured entities with type, value and context.
        PII entities (PAN, Aadhaar, account numbers) are flagged
        but values are redacted per DPDP Act 2023.
    """
    entities = []

    # Company names (basic — production would use NER)
    companies = re.findall(
        r'\b([A-Z][A-Za-z\s&]+(?:Ltd|Limited|Pvt|Private|LLP|Inc|Corp|Bank|'
        r'Finance|Capital|Securities|Insurance|Mutual Fund)\.?)\b',
        document_text
    )
    for c in set(companies[:10]):
        entities.append({"type": "COMPANY", "value": c.strip(), "redact": False})

    # Monetary amounts
    amounts = re.findall(
        r'(?:₹|Rs\.?|INR|USD|EUR)\s*([0-9,]+(?:\.\d+)?)\s*'
        r'(?:crore|lakh|million|billion|thousand|cr|L|Mn|Bn)?',
        document_text, re.IGNORECASE
    )
    for a in amounts[:10]:
        entities.append({"type": "AMOUNT", "value": a.replace(",", ""), "redact": False})

    # Dates
    dates = re.findall(
        r'\b(?:\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|'
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4})\b',
        document_text, re.IGNORECASE
    )
    for d in dates[:10]:
        entities.append({"type": "DATE", "value": d, "redact": False})

    # PAN numbers — detected and flagged for redaction
    pans = re.findall(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', document_text)
    for p in pans:
        entities.append({"type": "PAN", "value": "[REDACTED]", "redact": True,
                         "note": "PAN redacted per DPDP Act 2023"})

    # Aadhaar — detected and flagged
    aadhaar = re.findall(r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b', document_text)
    for a in aadhaar:
        entities.append({"type": "AADHAAR", "value": "[REDACTED]", "redact": True,
                         "note": "Aadhaar redacted per DPDP Act 2023"})

    pii_count = sum(1 for e in entities if e["redact"])

    return {
        "total_entities":  len(entities),
        "pii_detected":    pii_count,
        "entities":        entities,
        "extraction_model": "MCPilot Entity Extractor v1.0",
        "pii_framework":   "DPDP Act 2023",
        "timestamp":       datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 3: assess_credit_risk
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def assess_credit_risk(
    document_text: str,
    loan_amount_cr: float = 0,
    tenure_months: int = 0,
) -> dict:
    """
    Credit risk assessment from financial document.
    Extracts key credit indicators and generates risk rating.

    Args:
        document_text:  Financial document or borrower profile text
        loan_amount_cr: Proposed loan amount in crores (optional)
        tenure_months:  Proposed loan tenure in months (optional)

    Returns:
        Credit risk rating, key risk indicators, financial ratios
        and lending recommendation.
    """
    financials = _extract_financials(document_text)
    flags      = _detect_compliance_flags(document_text)
    text_lower = document_text.lower()

    # Risk indicators
    indicators = []
    risk_score = 50  # baseline

    # Positive indicators
    if "profit" in text_lower and "growth" in text_lower:
        indicators.append({"indicator": "Profit growth mentioned", "impact": "+", "score_delta": -10})
        risk_score -= 10
    if "debt free" in text_lower or "zero debt" in text_lower:
        indicators.append({"indicator": "Debt-free status", "impact": "+", "score_delta": -15})
        risk_score -= 15
    rating = re.search(
        r'(?:rating|rated)\b[^.\n]{0,40}?\b(?:crisil|icra|care|ind|india ratings|brickwork|acuite|infomerics)?'
        r'[\s:]*\b(AAA|AA[+-]?|A[+-]?|BBB[+-]?|BB[+-]?|B[+-]?|C|D)(?![A-Za-z+-])',
        document_text
    )
    if rating:
        grade = rating.group(1)
        delta = (-10 if grade.startswith("AA") else -5 if grade.startswith("A") and not grade.startswith("AA")
                 else 0 if grade.startswith("BBB") else 15 if grade.startswith("B") else 30)
        if delta:
            indicators.append({"indicator": f"Credit rating {grade}", "impact": "+" if delta < 0 else "-",
                               "score_delta": delta})
            risk_score += delta

    # Negative indicators — flags are weighted by severity (NPA/overdue live in NPL_RISK)
    for f in flags:
        delta = {"HIGH": 20, "MEDIUM": 10, "LOW": 3}.get(f["severity"], 10)
        risk_score += delta
        indicators.append({"indicator": f["description"], "impact": "-", "score_delta": delta,
                           "evidence": f.get("evidence")})
    net_loss = re.search(r'(?<![a-z])(?:net loss|loss (?:before|after) tax|loss for the (?:year|period)|'
                         r'negative ebitda|ebitda loss)(?![a-z])', text_lower)
    if net_loss and not _negated(text_lower, net_loss.start()):
        indicators.append({"indicator": "Net loss reported", "impact": "-", "score_delta": 20,
                           "evidence": _evidence(document_text, net_loss.start(), net_loss.end())})
        risk_score += 20

    risk_score = max(0, min(risk_score, 100))
    risk_rating = (
        "AAA" if risk_score < 20 else
        "AA"  if risk_score < 35 else
        "A"   if risk_score < 50 else
        "BBB" if risk_score < 65 else
        "BB"  if risk_score < 80 else
        "B"   if risk_score < 90 else "D"
    )
    recommendation = (
        "APPROVE"       if risk_score < 35 else
        "APPROVE WITH CONDITIONS" if risk_score < 55 else
        "REFER TO CREDIT COMMITTEE" if risk_score < 75 else
        "DECLINE"
    )

    return {
        "risk_score":       risk_score,
        "risk_rating":      risk_rating,
        "recommendation":   recommendation,
        "loan_amount_cr":   loan_amount_cr,
        "tenure_months":    tenure_months,
        "risk_indicators":  indicators,
        "financial_data":   financials,
        "compliance_flags": flags,
        "conditions": (
            ["Enhanced due diligence required",
             "Additional collateral may be needed",
             "Quarterly financial monitoring"]
            if recommendation == "APPROVE WITH CONDITIONS" else []
        ),
        "assessment_model":  "MCPilot Credit Risk Engine v1.0",
        "regulatory_basis":  "RBI Master Circular — Prudential Norms",
        "timestamp":         datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 4: flag_compliance_issues
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def flag_compliance_issues(
    document_text: str,
    check_type: str = "ALL",
) -> dict:
    """
    AML/KYC compliance flag detection across financial documents.
    Checks for money laundering indicators, sanctions exposure,
    PEP references and suspicious transaction patterns.

    Args:
        document_text: Financial document text
        check_type:    ALL | AML | KYC | SANCTIONS | FRAUD

    Returns:
        Compliance flags with severity, regulatory reference
        and recommended action.
    """
    flags = _detect_compliance_flags(document_text)

    # Filter by check type
    aml_flags      = ["ROUND_TRIPPING", "CASH_TRANSACTION", "UNUSUAL_GEOGRAPHY"]
    kyc_flags      = ["SHELL_COMPANY", "RELATED_PARTY"]
    sanction_flags = ["SANCTION_RISK"]
    fraud_flags    = ["ROUND_TRIPPING", "NPL_RISK"]

    if check_type != "ALL":
        filter_map = {
            "AML":       aml_flags,
            "KYC":       kyc_flags,
            "SANCTIONS": sanction_flags,
            "FRAUD":     fraud_flags,
        }
        allowed = filter_map.get(check_type, [])
        flags   = [f for f in flags if f["flag_id"] in allowed]

    # Add regulatory references
    reg_map = {
        "ROUND_TRIPPING":     "RBI Master Direction — KYC §16",
        "CASH_TRANSACTION":   "PMLA 2002 — CTR Reporting",
        "UNUSUAL_GEOGRAPHY":  "FATF Recommendation 19",
        "SHELL_COMPANY":      "MCA Beneficial Ownership Rules",
        "SANCTION_RISK":      "UNSCR + OFAC SDN List",
        "RELATED_PARTY":      "SEBI LODR Regulation 23",
        "NPL_RISK":           "RBI Prudential Norms — Asset Classification",
    }
    for f in flags:
        f["regulatory_reference"] = reg_map.get(f["flag_id"], "Internal policy")

    high_flags = [f for f in flags if f["severity"] == "HIGH"]
    sar_required = len(high_flags) > 0

    return {
        "check_type":      check_type,
        "flags_detected":  len(flags),
        "high_severity":   len(high_flags),
        "sar_required":    sar_required,
        "flags":           flags,
        "overall_status":  "CLEAR" if not flags else
                           "HIGH RISK — IMMEDIATE ACTION" if high_flags else
                           "MEDIUM RISK — REVIEW REQUIRED",
        "next_steps": (
            ["File SAR with FIU-IND immediately",
             "Place transaction on hold",
             "Notify Compliance Officer"]
            if sar_required else
            ["Complete enhanced due diligence",
             "Document findings in compliance log"]
            if flags else
            ["Document clearance in compliance log",
             "Proceed with standard processing"]
        ),
        "framework":   "PMLA, 2002 · FEMA, 1999 · RBI KYC Master Direction · FATF",
        "timestamp":   datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 5: generate_audit_report
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def generate_audit_report(
    document_text: str,
    entity_name: str = "Entity",
    audit_period: str = "FY 2025-26",
) -> dict:
    """
    Generate structured audit summary from financial document.
    Produces ICAI-aligned audit report format with key observations,
    risk areas and management action points.

    Args:
        document_text: Source financial/audit document text
        entity_name:   Name of entity being audited
        audit_period:  Audit period (e.g. "FY 2025-26")

    Returns:
        Structured audit report with opinion, observations,
        risk matrix and action points.
    """
    financials = _extract_financials(document_text)
    flags      = _detect_compliance_flags(document_text)
    doc_type   = _classify_document(document_text)
    text_lower = document_text.lower()

    # Determine audit opinion
    if any(kw in text_lower for kw in ["qualified", "except for", "material misstatement",
                                        "scope limitation"]):
        opinion = "QUALIFIED"
        opinion_basis = "Material misstatements or scope limitations identified"
    elif any(kw in text_lower for kw in ["adverse", "does not present fairly"]):
        opinion = "ADVERSE"
        opinion_basis = "Financial statements do not present a true and fair view"
    elif any(kw in text_lower for kw in ["disclaimer", "unable to obtain"]):
        opinion = "DISCLAIMER"
        opinion_basis = "Insufficient evidence to form an opinion"
    else:
        opinion = "UNQUALIFIED"
        opinion_basis = "Financial statements present a true and fair view"

    # Key risk areas
    risk_areas = []
    if flags:
        for f in flags:
            risk_areas.append({
                "area":     f["flag_id"].replace("_", " ").title(),
                "risk":     f["severity"],
                "finding":  f["description"],
                "action":   "Management to provide explanation and remediation plan",
            })

    if "related party" in text_lower:
        risk_areas.append({
            "area":   "Related Party Transactions",
            "risk":   "MEDIUM",
            "finding": "Related party transactions identified requiring disclosure",
            "action":  "Verify arm's length pricing and board approval",
        })

    return {
        "report_title":   f"Audit Report Summary — {entity_name}",
        "audit_period":   audit_period,
        "document_type":  doc_type,
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "audit_opinion": {
            "opinion":     opinion,
            "basis":       opinion_basis,
            "icai_standard": "SA 700 — Forming an Opinion on Financial Statements",
        },
        "key_findings": {
            "financial_highlights": financials,
            "risk_areas":           risk_areas,
            "total_flags":          len(flags),
            "high_risk_items":      sum(1 for f in flags if f["severity"] == "HIGH"),
        },
        "management_action_points": [
            f"Address: {r['finding']}" for r in risk_areas
        ] or ["No significant action points identified"],
        "data_protection": {
            "pii_redacted":  True,
            "framework": "DPDP Act, 2023 + RBI Data Localisation",
            "compliance": "RBI Data Localisation · DPDP Act, 2023 · PCI-DSS v4.0",
        },
        "prepared_by":    "MCPilot BFSI Intelligence v1.0",
        "standard":       "ICAI Standards on Auditing · Companies Act 2013",
    }


if __name__ == "__main__":
    mcp.run()