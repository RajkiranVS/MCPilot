"""
MCPilot — BFSI server compliance-flag and scoring tests
Legitimate documents must not trip AML/KYC flags on routine wording;
genuine risk indicators must still be caught. All entities are invented.
"""
import asyncio
from app.mcp.servers import bfsi_server as b

LEGIT_SANCTION_LETTER = """SANCTION LETTER
Sub: Sanction of Term Loan and Working Capital Facilities
We are pleased to inform you that the following credit facilities have been sanctioned to your company:
1. Term Loan: Rs. 25 crore for capacity expansion, tenor 7 years
- Overdue interest of 2% p.a. applies on any overdue amount.
- Event of Default: non-payment of any instalment within 30 days shall constitute an event of default.
- The project is implemented directly by the company; no special purpose vehicle (SPV) is involved.
- The company's 26% shareholder, Example Holdings Ltd, is incorporated in Mauritius (FDI, automatic route).
Revenue from operations: 182.4 crore; Net profit: 14.8 crore. Total assets: 240.6 crore.
Statement of Profit and Loss and related party transactions are disclosed as per Ind AS 24.
Credit rating: CARE A+ (Stable). The company has no overdue loans and is not classified as an NPA by any lender.
"""

FUND_FACTSHEET = """Example Mutual Fund — Annual Report and Fund Factsheet
The AMC is engaged in managing offshore and global funds through Example AMC (Mauritius) Limited.
Brokerage paid to Group & Associate Company: 0.01% of total brokerage.
Securities classified as below investment grade or default as at March 31, 2026: Nil.
Markets were volatile: crude prices spiked after the Iran war.
"""


def flag_ids(text):
    return {f["flag_id"] for f in b._detect_compliance_flags(text)}


def test_legit_sanction_letter_raises_no_flags():
    # "sanctioned" (= approved), "event of default", "no SPV", Mauritius FDI,
    # Ind AS 24 disclosure, "not ... an NPA" are all routine
    assert flag_ids(LEGIT_SANCTION_LETTER) == set()


def test_fund_factsheet_raises_no_flags():
    assert flag_ids(FUND_FACTSHEET) == set()


def test_genuine_red_flags_still_detected():
    text = ("The borrower routed funds through a shell company with nominee directors. "
            "Accounts show frequent cash deposits just below the reporting threshold. "
            "The counterparty is a sanctioned entity on the OFAC SDN list. "
            "Payments to Iran were made via a third bank. "
            "The account has been classified as a non-performing asset.")
    assert {"SHELL_COMPANY", "CASH_TRANSACTION", "SANCTION_RISK",
            "UNUSUAL_GEOGRAPHY", "NPL_RISK"} <= flag_ids(text)


def test_flags_carry_evidence():
    flags = b._detect_compliance_flags("Funds were moved via a shell company in 2024.")
    assert flags[0]["flag_id"] == "SHELL_COMPANY"
    assert "shell company" in flags[0]["evidence"]


def test_negation_cancels_flag():
    assert flag_ids("The company is not a shell company.") == set()
    assert "SHELL_COMPANY" in flag_ids("The company is a shell company.")


def test_geography_needs_exposure_context():
    assert flag_ids("Crude prices rose before the Iran war.") == set()
    assert "UNUSUAL_GEOGRAPHY" in flag_ids("The supplier is incorporated in Iran.")


def test_geography_list_is_configurable(monkeypatch):
    monkeypatch.setenv("BFSI_HIGH_RISK_JURISDICTIONS", "Ruritania")
    assert "UNUSUAL_GEOGRAPHY" in flag_ids("Remittances to Ruritania were frequent.")
    assert flag_ids("Remittances to Iran were frequent.") == set()


def test_classifier():
    assert b._classify_document(LEGIT_SANCTION_LETTER) == "LOAN_DOCUMENT"
    assert b._classify_document(FUND_FACTSHEET) == "ANNUAL_REPORT"


def test_credit_risk_not_penalised_by_routine_wording():
    r = b.assess_credit_risk(LEGIT_SANCTION_LETTER)
    deltas = {i["indicator"]: i["score_delta"] for i in r["risk_indicators"]}
    assert "Net loss reported" not in deltas        # "Profit and Loss" is not a loss
    assert deltas.get("Credit rating A+") == -5
    assert r["recommendation"] != "DECLINE"
    assert b.flag_compliance_issues(LEGIT_SANCTION_LETTER)["sar_required"] is False


def test_credit_risk_detects_actual_loss():
    r = b.assess_credit_risk("The company reported a net loss of Rs 12 crore for FY26.")
    assert any(i["indicator"] == "Net loss reported" for i in r["risk_indicators"])


def test_summary_without_local_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    s = asyncio.run(b.summarise_financial_document(LEGIT_SANCTION_LETTER))
    assert s["ai_summary"]["status"] == "UNAVAILABLE"
    assert s["risk_assessment"]["risk_level"] == "LOW"
    assert s["compliance_flags"] == []
