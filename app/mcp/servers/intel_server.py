"""
MCPilot — Naval Intelligence Fusion Server
DISC 14 PS 34: Sovereign Multi-Modal AI Foundation Model for Indian Navy

Maps to PS 34 key application areas:
  - Multi-source intelligence fusion + order-of-battle extraction  (§a)
  - Mission planning support + COA generation                      (§b)
  - Cyber and EW threat analysis                                   (§d)
  - Classification-aware RAG over naval knowledge repositories     (§core)

Classification: SECRET
Access: navy-ops, navy-intel, iaf-ops (via clearance registry)
Denied: icg-watchkeeper, dev-tenant, army-field (insufficient clearance)

Run: python app/mcp/servers/intel_server.py
"""
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("Naval Intelligence Server")

# ── Simulated intelligence database ──────────────────────────────────────────
# Realistic but fictional naval intelligence data for demo purposes

_VESSEL_INTELLIGENCE = {
    "ALPHA-TANGO-7": {
        "track_id":       "ALPHA-TANGO-7",
        "classification": "SECRET",
        "vessel_type":    "Type-052D Destroyer",
        "flag":           "UNKNOWN",
        "last_position":  "12.44N, 65.22E",
        "speed_kts":      18.4,
        "course":         285,
        "confidence":     87,
        "sources":        ["SIGINT", "SATINT", "AIS-DARK"],
        "threat_level":   "HIGH",
        "notes":          "Extended patrol pattern, Arabian Sea approaches. "
                          "AIS suppressed since 0400Z. SIGINT intercepts suggest "
                          "active radar emissions consistent with fire control.",
    },
    "BRAVO-SIERRA-3": {
        "track_id":       "BRAVO-SIERRA-3",
        "classification": "SECRET",
        "vessel_type":    "Submarine — SSK Class",
        "flag":           "UNKNOWN",
        "last_position":  "CLASSIFIED",
        "speed_kts":      8.0,
        "course":         None,
        "confidence":     62,
        "sources":        ["SOSUS", "HUMINT"],
        "threat_level":   "CRITICAL",
        "notes":          "Subsurface contact. SOSUS correlation gives 62% confidence. "
                          "Last confirmed position Bay of Bengal northern approaches. "
                          "Possible patrol of SLOC.",
    },
    "CHARLIE-FOXTROT-1": {
        "track_id":       "CHARLIE-FOXTROT-1",
        "classification": "CONFIDENTIAL",
        "vessel_type":    "Intelligence Collection Vessel",
        "flag":           "UNKNOWN",
        "last_position":  "8.12N, 77.88E",
        "speed_kts":      3.2,
        "course":         112,
        "confidence":     94,
        "sources":        ["AIS", "SATINT", "HUMINT"],
        "threat_level":   "MEDIUM",
        "notes":          "Persistent loiter in Gulf of Mannar. "
                          "Electronic emissions consistent with SIGINT collection. "
                          "Cross-referenced with known SIGINT vessel profiles.",
    },
}

_THREAT_ASSESSMENTS = [
    {
        "id":             "TA-2026-0441",
        "classification": "SECRET",
        "date":           "2026-04-14",
        "title":          "Increased Submarine Activity — Arabian Sea",
        "summary":        "Three credible SSK contacts in last 72 hours. "
                          "Pattern consistent with SLOC interdiction preparation.",
        "confidence":     78,
        "sources":        ["SIGINT", "HUMINT", "IMINT"],
        "recommended_action": "Task P-8I for ASW sweep. Alert Eastern Naval Command.",
        "threat_level":   "HIGH",
    },
    {
        "id":             "TA-2026-0438",
        "classification": "SECRET",
        "date":           "2026-04-13",
        "title":          "Surface Group Transit — Malacca Strait Egress",
        "summary":        "SATINT confirms 3-vessel surface group transiting "
                          "Malacca Strait westbound. Destroyer + 2 frigates. "
                          "Projected IOR arrival 96 hours.",
        "confidence":     91,
        "sources":        ["SATINT", "AIS"],
        "recommended_action": "Shadow with P-8I. Task INS Kolkata for intercept option.",
        "threat_level":   "MEDIUM",
    },
    {
        "id":             "TA-2026-0435",
        "classification": "TOP_SECRET",
        "date":           "2026-04-12",
        "title":          "SIGINT: Encrypted Comms Surge — PLAN HQ",
        "summary":        "[CONTENT RESTRICTED — TOP SECRET CODEWORD]",
        "confidence":     None,
        "sources":        ["SIGINT-CODEWORD"],
        "recommended_action": "[RESTRICTED]",
        "threat_level":   "CRITICAL",
    },
]

_ORDER_OF_BATTLE = {
    "friendly": {
        "classification": "SECRET",
        "date":           "2026-04-14T06:00:00Z",
        "units": [
            {"unit": "INS Vikrant", "type": "Carrier", "position": "CLASSIFIED", "status": "OPERATIONAL", "task": "STRIKE GROUP LEAD"},
            {"unit": "INS Kolkata", "type": "Destroyer", "position": "CLASSIFIED", "status": "OPERATIONAL", "task": "AAW ESCORT"},
            {"unit": "INS Shivalik", "type": "Frigate",  "position": "CLASSIFIED", "status": "OPERATIONAL", "task": "ASW SCREEN"},
            {"unit": "INS Arihant", "type": "SSBN",      "position": "CLASSIFIED", "status": "OPERATIONAL", "task": "STRATEGIC DETERRENT"},
            {"unit": "P-8I Alpha", "type": "MPA",        "position": "CLASSIFIED", "status": "AIRBORNE",    "task": "ASW PATROL"},
        ],
    },
    "adversary": {
        "classification": "SECRET",
        "date":           "2026-04-14T06:00:00Z",
        "units": [
            {"unit": "ALPHA-TANGO-7", "type": "Destroyer",   "position": "12.44N 65.22E", "status": "ACTIVE", "task": "PATROL"},
            {"unit": "BRAVO-SIERRA-3","type": "Submarine",    "position": "CLASSIFIED",   "status": "SUBMERGED","task": "UNKNOWN"},
            {"unit": "CHARLIE-FOXTROT-1","type": "SIGINT Vessel","position": "8.12N 77.88E","status": "LOITERING","task": "ISR"},
        ],
    },
}

_COURSES_OF_ACTION = {
    "DEFENSIVE": {
        "coa_id":   "COA-DEF-001",
        "name":     "Defensive Perimeter",
        "posture":  "DEFENSIVE",
        "summary":  "Establish layered ASW screen around carrier group. "
                    "P-8I continuous patrol of submarine threat axes. "
                    "INS Arihant remains at strategic alert posture.",
        "units_tasked": ["INS Vikrant", "INS Kolkata", "INS Shivalik", "P-8I Alpha"],
        "risk":     "LOW",
        "timeline": "0-12 hours",
    },
    "INTERCEPT": {
        "coa_id":   "COA-INT-002",
        "name":     "Surface Group Intercept",
        "posture":  "ASSERTIVE",
        "summary":  "Task INS Kolkata + INS Shivalik for intercept of approaching "
                    "surface group. Maintain 12nm standoff. Broadcast MMSI challenge.",
        "units_tasked": ["INS Kolkata", "INS Shivalik"],
        "risk":     "MEDIUM",
        "timeline": "12-24 hours",
    },
    "SURGE": {
        "coa_id":   "COA-SRG-003",
        "name":     "ASW Surge",
        "posture":  "OFFENSIVE",
        "summary":  "Task all available ASW assets for prosecution of BRAVO-SIERRA-3. "
                    "Request additional P-8I sorties. Alert SSBN for counter-positioning.",
        "units_tasked": ["P-8I Alpha", "INS Shivalik", "INS Arihant"],
        "risk":     "HIGH",
        "timeline": "0-6 hours",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 1: fuse_intelligence
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def fuse_intelligence(query: str, classification_floor: str = "CONFIDENTIAL") -> dict:
    """
    Multi-source intelligence fusion — aggregates SIGINT, HUMINT,
    SATINT and AIS intelligence into a single fused assessment.

    This is the core capability of PS 34 §(a): multi-source intelligence
    fusion, summarization and order-of-battle extraction.

    Args:
        query:                Natural language intelligence query
        classification_floor: Minimum classification level to include
                              (CONFIDENTIAL | SECRET | TOP_SECRET)

    Returns:
        Fused intelligence picture with source attribution,
        confidence scores and recommended actions.
    """
    level_order = {"UNCLASSIFIED": 0, "RESTRICTED": 1, "CONFIDENTIAL": 2,
                   "SECRET": 3, "TOP_SECRET": 4}
    floor = level_order.get(classification_floor.upper(), 2)

    q = query.lower()

    # Collect relevant intelligence
    relevant_tracks = []
    for track in _VESSEL_INTELLIGENCE.values():
        track_level = level_order.get(track["classification"], 2)
        if track_level >= floor:
            relevant_tracks.append(track)

    relevant_threats = []
    for ta in _THREAT_ASSESSMENTS:
        ta_level = level_order.get(ta["classification"], 2)
        if ta_level >= floor:
            if any(kw in q for kw in ["threat", "submarine", "surface", "all", "assessment"]):
                relevant_threats.append(ta)

    # Compute overall threat picture
    threat_levels = [t.get("threat_level", "LOW") for t in relevant_tracks]
    overall = "CRITICAL" if "CRITICAL" in threat_levels else \
              "HIGH"     if "HIGH"     in threat_levels else \
              "MEDIUM"   if "MEDIUM"   in threat_levels else "LOW"

    return {
        "query":               query,
        "classification":      "SECRET",
        "fusion_timestamp":    datetime.now(timezone.utc).isoformat(),
        "overall_threat_level": overall,
        "tracks_fused":        len(relevant_tracks),
        "threat_assessments":  len(relevant_threats),
        "vessel_tracks":       relevant_tracks,
        "threat_assessments_detail": [
            ta for ta in relevant_threats
            if level_order.get(ta["classification"], 2) <= floor + 1
        ],
        "sources_used":        ["SIGINT", "HUMINT", "SATINT", "AIS", "SOSUS"],
        "fusion_confidence":   82,
        "recommended_action":  relevant_threats[0]["recommended_action"]
                               if relevant_threats else "Continue routine surveillance",
        "reporting_officer":   "MCPilot Intel Fusion v1.0 — PS 34 §(a)",
    }


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 2: get_order_of_battle
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def get_order_of_battle(force: str = "ALL") -> dict:
    """
    Retrieve current order of battle — friendly and adversary unit dispositions.
    Classification: SECRET.

    Args:
        force: FRIENDLY | ADVERSARY | ALL

    Returns:
        Current OOB with unit positions, status and tasking.
        Friendly positions are always classified — shown as CLASSIFIED.
        Adversary positions shown at confidence level.
    """
    result = {
        "classification": "SECRET",
        "as_of":          _ORDER_OF_BATTLE["friendly"]["date"],
        "timestamp":      datetime.now(timezone.utc).isoformat(),
    }

    if force in ("FRIENDLY", "ALL"):
        result["friendly_oob"] = _ORDER_OF_BATTLE["friendly"]

    if force in ("ADVERSARY", "ALL"):
        result["adversary_oob"] = _ORDER_OF_BATTLE["adversary"]

    result["total_friendly_units"] = len(_ORDER_OF_BATTLE["friendly"]["units"])
    result["total_adversary_contacts"] = len(_ORDER_OF_BATTLE["adversary"]["units"])
    result["reporting_officer"] = "MCPilot Intel Fusion v1.0 — PS 34 §(a)"

    return result


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 3: generate_coa
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def generate_coa(threat_id: str = "", posture: str = "ALL") -> dict:
    """
    Generate Courses of Action (COA) for mission planning.
    Maps to PS 34 §(b): Mission planning support and COA generation.

    Args:
        threat_id: Specific threat track ID to plan against (optional)
        posture:   DEFENSIVE | ASSERTIVE | OFFENSIVE | ALL

    Returns:
        Recommended COAs with unit tasking, risk assessment
        and execution timeline.
    """
    if posture == "ALL":
        coas = list(_COURSES_OF_ACTION.values())
    else:
        coas = [c for c in _COURSES_OF_ACTION.values()
                if c["posture"] == posture.upper()]

    # If specific threat provided, filter relevant COAs
    if threat_id and threat_id in _VESSEL_INTELLIGENCE:
        threat = _VESSEL_INTELLIGENCE[threat_id]
        threat_level = threat["threat_level"]
        if threat_level == "CRITICAL":
            coas = [_COURSES_OF_ACTION["SURGE"]]
        elif threat_level == "HIGH":
            coas = [_COURSES_OF_ACTION["INTERCEPT"], _COURSES_OF_ACTION["DEFENSIVE"]]

    return {
        "classification":   "SECRET",
        "threat_id":        threat_id or "GENERAL",
        "posture_requested": posture,
        "coas_generated":   len(coas),
        "courses_of_action": coas,
        "recommended_coa":  coas[0]["coa_id"] if coas else None,
        "planning_basis":   "Current OOB + threat assessments as of "
                            f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}",
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "reporting_officer": "MCPilot Intel Fusion v1.0 — PS 34 §(b)",
    }


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 4: assess_ew_threat
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def assess_ew_threat(platform: str = "", frequency_band: str = "") -> dict:
    """
    Electronic Warfare and cyber threat assessment.
    Maps to PS 34 §(d): Cyber and EW threat analysis and indicator enrichment.

    Args:
        platform:        Specific platform to assess (optional)
        frequency_band:  Frequency band of interest (X, S, L, C, Ku)

    Returns:
        EW threat assessment with emission profiles, jamming risk
        and recommended counter-measures.
    """
    # Simulated EW threat database
    ew_threats = [
        {
            "emitter_id":    "EW-ALPHA-001",
            "classification": "SECRET",
            "platform":      "ALPHA-TANGO-7",
            "emission_type": "Fire Control Radar",
            "frequency_band": "X",
            "pulse_width_us": 2.4,
            "prf_hz":        1200,
            "threat_level":  "HIGH",
            "jamming_risk":  "MEDIUM",
            "counter_measure": "Activate DRFM jammer. Enable chaff dispensing. "
                               "Manoeuvre to break radar lock.",
        },
        {
            "emitter_id":    "EW-BRAVO-002",
            "classification": "SECRET",
            "platform":      "CHARLIE-FOXTROT-1",
            "emission_type": "SIGINT Collection",
            "frequency_band": "S",
            "pulse_width_us": None,
            "prf_hz":        None,
            "threat_level":  "MEDIUM",
            "jamming_risk":  "LOW",
            "counter_measure": "Enforce EMCON. Route classified comms via SATCOM only.",
        },
    ]

    # Filter if platform specified
    if platform:
        ew_threats = [t for t in ew_threats
                      if platform.upper() in t["platform"].upper()]
    if frequency_band:
        ew_threats = [t for t in ew_threats
                      if t["frequency_band"] == frequency_band.upper()]

    overall_ew_threat = "HIGH" if any(t["threat_level"] == "HIGH" for t in ew_threats) \
                        else "MEDIUM" if ew_threats else "LOW"

    return {
        "classification":    "SECRET",
        "platform_filter":   platform or "ALL",
        "band_filter":       frequency_band or "ALL",
        "emitters_detected": len(ew_threats),
        "overall_ew_threat": overall_ew_threat,
        "ew_threats":        ew_threats,
        "emcon_recommended": overall_ew_threat in ("HIGH", "CRITICAL"),
        "timestamp":         datetime.now(timezone.utc).isoformat(),
        "reporting_officer": "MCPilot Intel Fusion v1.0 — PS 34 §(d)",
    }


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 5: query_naval_rag
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def query_naval_rag(query: str, domain: str = "ALL") -> dict:
    """
    RAG-enabled query over naval knowledge repositories.
    Maps to PS 34 core requirement: RAG over naval knowledge repositories.

    Domains: DOCTRINE | TACTICS | MAINTENANCE | SIGNALS | ALL

    Args:
        query:  Natural language query against naval knowledge base
        domain: Knowledge domain to search

    Returns:
        Retrieved passages with source citations, confidence scores
        and cross-references to relevant doctrine/procedures.
    """
    q = query.lower()
    domain = domain.upper()

    # Simulated naval knowledge base
    kb = [
        {
            "doc_id":     "NWP-3-56",
            "title":      "Maritime Surface Warfare",
            "domain":     "DOCTRINE",
            "passage":    "ASW prosecution requires coordination between surface, "
                          "subsurface and aviation assets. P-8I/MH-60R coordination "
                          "procedures outlined in TACNOTE ASW-001.",
            "relevance":  0.87 if "asw" in q or "submarine" in q else 0.3,
            "classification": "RESTRICTED",
        },
        {
            "doc_id":     "EMCON-PROC-2024",
            "title":      "Emission Control Procedures",
            "domain":     "SIGNALS",
            "passage":    "EMCON Alpha: All non-essential emissions ceased. "
                          "EMCON Bravo: Reduced emissions, passive sensors only. "
                          "EMCON Charlie: Normal operations with emission control.",
            "relevance":  0.91 if "emcon" in q or "emission" in q or "ew" in q else 0.2,
            "classification": "RESTRICTED",
        },
        {
            "doc_id":     "IOPG-2025",
            "title":      "Indian Ocean Patrol Guidelines",
            "domain":     "TACTICS",
            "passage":    "SLOC protection in IOR requires 3-layer defence: "
                          "outer (350nm), middle (150nm) and inner (50nm) zones. "
                          "Coordination with Coast Guard for inner zone.",
            "relevance":  0.78 if "sloc" in q or "patrol" in q or "ior" in q else 0.25,
            "classification": "CONFIDENTIAL",
        },
        {
            "doc_id":     "COE-ASW-2026",
            "title":      "ASW Centre of Excellence — Tactical Bulletin",
            "domain":     "TACTICS",
            "passage":    "Recent SSK contacts suggest evolution in patrol patterns. "
                          "Recommend barrier ASW with LOFAR buoy fields at depth "
                          "gradient layers.",
            "relevance":  0.82 if "ssb" in q or "contact" in q or "asw" in q else 0.15,
            "classification": "SECRET",
        },
    ]

    # Filter by domain
    if domain != "ALL":
        kb = [d for d in kb if d["domain"] == domain]

    # Sort by relevance
    kb.sort(key=lambda x: x["relevance"], reverse=True)
    results = [d for d in kb if d["relevance"] > 0.3]

    return {
        "query":           query,
        "domain":          domain,
        "classification":  "SECRET",
        "results_found":   len(results),
        "results":         results[:4],
        "kb_size":         "12,847 naval doctrine documents indexed",
        "rag_model":       "MCPilot RAG — BGE embeddings, ChromaDB",
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "reporting_officer": "MCPilot Intel Fusion v1.0 — PS 34 RAG",
    }


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 6: get_sigint_summary
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def get_sigint_summary(time_window_hrs: int = 24) -> dict:
    """
    SIGINT intercept summary for the specified time window.
    Classification: TOP_SECRET — triggers classification gating for
    tenants without TOP_SECRET clearance.

    Args:
        time_window_hrs: Hours of SIGINT data to summarise (default 24)

    Returns:
        SIGINT summary with intercept count, key indicators and
        analysis. TOP_SECRET content — requires TS clearance.
    """
    return {
        "classification":    "TOP_SECRET",
        "time_window_hrs":   time_window_hrs,
        "period":            f"Last {time_window_hrs} hours",
        "intercepts_total":  847,
        "intercepts_flagged": 23,
        "key_indicators": [
            "Surge in encrypted comms on naval frequencies — possible exercise or operation",
            "Frequency hop pattern consistent with known adversary submarine comms",
            "Bearing lines from 3 shore stations converge on BRAVO-SIERRA-3 last position",
        ],
        "analysis": "[TOP SECRET CODEWORD] — Full analysis restricted to "
                    "personnel with TOP SECRET clearance and appropriate codeword access.",
        "analyst":   "SIGINT Processing Cell — Naval Intelligence Directorate",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reporting_officer": "MCPilot Intel Fusion v1.0 — PS 34 SIGINT",
    }


if __name__ == "__main__":
    mcp.run()