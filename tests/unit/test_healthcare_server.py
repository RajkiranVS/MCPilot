"""
MCPilot — Healthcare server extraction tests
Synthetic outpatient note in the layout Indian hospital EMRs print
(labelled vitals, "O/e", "Imp", "Advice"). All patient data is invented.
"""
import asyncio
import pytest
from app.mcp.servers import healthcare_server as hs

OPD_NOTE = """OUTPATIENT RECORD
Hospital No: [CLINICAL_ID] Visit No: [CLINICAL_ID]
Name: [PERSON] Age/Sex: 52 Yrs/Female
BP Systolic: 150 mmHg BP Diastolic: 94 mmHg Pulse Rate: 112 bt/min
Respiration: 18 br/min Temperature: 98.6 °F Weight: 71 kg
OPD Notes :
Fall from stairs two days ago. Fell on left side.
Pain and swelling over left ankle.
O/e:
Tenderness over lateral malleolus. Ankle movements restricted by pain.
Imp
Suspected left lateral malleolus fracture
Advice:
X-ray left ankle AP/lateral. Tab. Paracetamol 650mg SOS.
"""


def test_opd_note_classified_as_clinical_notes():
    # "mg"/"od" substrings used to misfire as PRESCRIPTION
    assert hs._classify_clinical_document(OPD_NOTE) == "CLINICAL_NOTES"
    assert hs._classify_clinical_document("Referred for NCS/EMG study") != "PRESCRIPTION"


def test_classifier_still_detects_prescriptions_and_labs():
    rx = "Rx\nTab. Metformin 500mg BD\nTab. Atorvastatin 10mg HS\nCap. Omeprazole 20mg OD"
    assert hs._classify_clinical_document(rx) == "PRESCRIPTION"
    lab = "LABORATORY REPORT\nHaemoglobin 11.2 g/dL\nCreatinine 1.1 mg/dL\nPlatelets 2.1 lakh"
    assert hs._classify_clinical_document(lab) == "LAB_REPORT"


def test_vitals_with_separately_labelled_bp_and_pulse_rate():
    v = hs._extract_vitals(OPD_NOTE)
    assert v["blood_pressure"] == "150/94 mmHg"
    assert v["bp_status"] == "HYPERTENSIVE"
    assert v["pulse"] == "112 bpm"
    assert v["pulse_status"] == "TACHYCARDIC"
    assert v["respiratory_rate"] == "18/min"
    assert v["temperature"] == "98.6°F"
    assert v["weight"] == "71 kg"


def test_vitals_compact_formats_still_work():
    v = hs._extract_vitals("BP 120/80, HR 72, SpO2 97%, RR 16, Temp 37.2 C, Wt 60 kg")
    assert v["blood_pressure"] == "120/80 mmHg"
    assert v["pulse"] == "72 bpm"
    assert v["spo2"] == "97%"
    assert v["respiratory_rate"] == "16/min"
    assert v["temperature"] == "37.2°C"


def test_vital_labels_must_be_whole_words():
    # "hr" inside "chronic", "t" inside "at" must not produce vitals
    v = hs._extract_vitals("Chronic 45 day history, seen at 10 am.")
    assert "pulse" not in v and "temperature" not in v


def test_medications_no_false_positives_from_ordinary_words():
    meds = hs._extract_medications(OPD_NOTE)
    assert "side" not in meds
    assert "paracetamol" in meds


def test_medications_after_dosage_form_and_drug_suffixes():
    meds = hs._extract_medications("Tab. Pantocid 40mg OD, Inj Ceftriaxone 1g, losartan 50mg")
    assert {"pantocid", "ceftriaxone", "losartan"} <= set(meds)


def test_impression_abbreviation_on_next_line():
    assert hs._extract_diagnoses(OPD_NOTE) == ["Suspected left lateral malleolus fracture"]


def test_sections_split_on_headings():
    s = hs._extract_sections(OPD_NOTE)
    assert "Fall from stairs" in s["history"]
    assert "lateral malleolus" in s["examination"]
    assert s["impression"] == "Suspected left lateral malleolus fracture"
    assert s["plan"].startswith("X-ray left ankle")


def test_summary_without_local_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    r = asyncio.run(hs.summarise_clinical_document(OPD_NOTE))
    assert r["document_type"] == "CLINICAL_NOTES"
    assert r["ai_summary"]["status"] == "UNAVAILABLE"
    assert r["risk_assessment"]["risk_level"] == "HIGH"       # hypertensive + tachycardic
    assert r["clinical_summary"]["impression"] == "Suspected left lateral malleolus fracture"


def test_summary_when_ollama_unreachable(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:9")   # nothing listens here
    monkeypatch.setenv("LOCAL_LLM_TIMEOUT", "2")
    r = asyncio.run(hs.summarise_clinical_document(OPD_NOTE))
    assert r["status"] == "OK"
    assert r["ai_summary"]["status"] == "UNAVAILABLE"
    assert r["vitals"]["pulse"] == "112 bpm"
