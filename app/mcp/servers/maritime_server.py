"""
MCPilot — Maritime Security MCP Server
DISC 14 PS 82: Maritime Security Analytics Software (MSAS)
Indian Coast Guard — Coastal Surveillance Network

Exposes six tools mapped directly to DISC 14 requirements:
  - get_vessel_track    : AIS track history + kinematics (PS 82 §3.4)
  - classify_vessel     : Vessel type + activity classification (PS 82 §3.1)
  - flag_anomaly        : Anomaly detection — loitering, spoofing, boundary (PS 82 §3.4)
  - get_risk_score      : Dynamic risk scoring + VOI ranking (PS 82 §3.6)
  - search_pans_data    : RAG over PANS / port notices (PS 82 §3.5)
  - investigate_vessel  : Full comprehensive MDA investigation report — fuses all data sources into single intelligence assessment.

Run: python app/mcp/servers/maritime_server.py
"""
import random
from datetime import datetime, timezone, timedelta
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Maritime Security Server")

# ── Simulated AIS vessel database ─────────────────────────────────────────────
# Realistic Indian coastal vessel data for demo purposes
_VESSEL_DB = {
    "419001234": {
        "mmsi": "419001234",
        "name": "MV COASTAL STAR",
        "flag": "India",
        "type": "Cargo",
        "imo": "9234567",
        "call_sign": "VTAS4",
        "gross_tonnage": 4200,
        "length": 98,
        "beam": 16,
        "draught": 5.8,
        "owner": "Coastal Shipping Ltd",
        "port_of_registry": "Mumbai",
        "last_known_port": "JNPT, Mumbai",
        "destination": "Kandla",
        "status": "ACTIVE",
    },
    "419005678": {
        "mmsi": "419005678",
        "name": "FV SAGAR MITRA",
        "flag": "India",
        "type": "Fishing",
        "imo": "N/A",
        "call_sign": "VKCH9",
        "gross_tonnage": 85,
        "length": 24,
        "beam": 6,
        "draught": 2.1,
        "owner": "Rajan Fisheries",
        "port_of_registry": "Kochi",
        "last_known_port": "Kochi Fishing Harbour",
        "destination": "At Sea",
        "status": "ACTIVE",
    },
    "419009999": {
        "mmsi": "419009999",
        "name": "UNKNOWN",
        "flag": "UNVERIFIED",
        "type": "Unknown",
        "imo": "UNVERIFIED",
        "call_sign": "DARK",
        "gross_tonnage": 0,
        "length": 0,
        "beam": 0,
        "draught": 0,
        "owner": "UNREGISTERED",
        "port_of_registry": "UNKNOWN",
        "last_known_port": "UNKNOWN",
        "destination": "UNKNOWN",
        "status": "DARK_VESSEL",
    },
    "419007788": {
        "mmsi": "419007788",
        "name": "MT PETROLINE",
        "flag": "India",
        "type": "Tanker",
        "imo": "9345678",
        "call_sign": "VRMS2",
        "gross_tonnage": 18500,
        "length": 168,
        "beam": 26,
        "draught": 10.2,
        "owner": "Hindustan Petro Marine",
        "port_of_registry": "Chennai",
        "last_known_port": "Paradip Port",
        "destination": "Ennore",
        "status": "ACTIVE",
    },
}

# ── Simulated PANS database ───────────────────────────────────────────────────
_PANS_DB = [
    {
        "pans_id": "PANS-ICG-2026-0341",
        "date": "2026-04-01",
        "title": "Temporary Prohibited Area — Gulf of Kutch Exercises",
        "area": "Gulf of Kutch",
        "lat_range": "22.5N-23.0N",
        "lon_range": "68.5E-69.5E",
        "valid_from": "2026-04-10",
        "valid_to": "2026-04-20",
        "details": "Naval exercises in progress. All merchant vessels to maintain 5nm standoff.",
        "authority": "FOCINC West",
    },
    {
        "pans_id": "PANS-ICG-2026-0298",
        "date": "2026-03-15",
        "title": "Notice to Mariners — Lakshadweep EEZ Boundary Reminder",
        "area": "Lakshadweep EEZ",
        "lat_range": "8.0N-12.5N",
        "lon_range": "71.0E-74.5E",
        "valid_from": "2026-03-15",
        "valid_to": "2026-12-31",
        "details": "Foreign fishing vessels strictly prohibited within 200nm EEZ. Violators will be intercepted.",
        "authority": "ICG District HQ Lakshadweep",
    },
    {
        "pans_id": "PANS-ICG-2026-0312",
        "date": "2026-03-22",
        "title": "Wreck Marking — Sunken Vessel Off Porbandar",
        "area": "Arabian Sea - Off Porbandar",
        "lat_range": "21.6N",
        "lon_range": "69.4E",
        "valid_from": "2026-03-22",
        "valid_to": "2026-09-30",
        "details": "Sunken vessel at 21.38N 69.61E. All vessels maintain 0.5nm clearance. Buoy marking installed.",
        "authority": "DGLL Mumbai",
    },
    {
        "pans_id": "PANS-ICG-2026-0355",
        "date": "2026-04-05",
        "title": "High Alert — Suspicious Dhow Activity Off Lakshadweep",
        "area": "Arabian Sea SW Approaches",
        "lat_range": "9.0N-11.0N",
        "lon_range": "72.0E-74.0E",
        "valid_from": "2026-04-05",
        "valid_to": "2026-04-30",
        "details": "Intelligence inputs indicate possible narcotic smuggling via dhow route. All ICG units to heighten watch.",
        "authority": "ICG HQ New Delhi — Intelligence Branch",
    },
]


def _generate_track(mmsi: str, hours: int = 6) -> list[dict]:
    """Generate realistic AIS track positions for demo."""
    vessel = _VESSEL_DB.get(mmsi, {})
    is_dark = vessel.get("status") == "DARK_VESSEL"
    is_fishing = vessel.get("type") == "Fishing"

    # Base position — Indian coastal waters
    base_lat = 15.5 + random.uniform(-3, 3)
    base_lon = 73.5 + random.uniform(-2, 4)

    track = []
    now = datetime.now(timezone.utc)

    for i in range(hours * 4):  # 15-min intervals
        t = now - timedelta(minutes=15 * (hours * 4 - i))

        if is_dark:
            # Dark vessel — sporadic, inconsistent positions
            if random.random() > 0.4:  # 60% reporting gap
                continue
            speed = random.uniform(0, 3)
            course = random.uniform(0, 360)
        elif is_fishing:
            # Fishing vessel — slow, erratic course (loitering pattern)
            speed = random.uniform(0.5, 4.5)
            course = (base_lat * 10 + i * 37) % 360  # erratic
        else:
            # Normal cargo/tanker — steady course and speed
            speed = random.uniform(8, 14)
            course = 45 + random.uniform(-5, 5)

        track.append({
            "timestamp": t.isoformat(),
            "lat": round(base_lat + (i * 0.002 * (1 if not is_fishing else random.uniform(-1, 1))), 4),
            "lon": round(base_lon + (i * 0.003 * (1 if not is_dark else random.uniform(-0.5, 0.5))), 4),
            "speed_kts": round(speed, 1),
            "course_deg": round(course, 1),
            "nav_status": "UNDER_WAY" if speed > 0.5 else "AT_ANCHOR",
            "reporting_interval_min": None if not is_dark else "IRREGULAR",
        })

    return track


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 1: get_vessel_track
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def get_vessel_track(mmsi: str, hours: int = 6) -> dict:
    """
    Retrieve AIS track history and kinematic data for a vessel.

    Args:
        mmsi: Maritime Mobile Service Identity number (9 digits)
        hours: Track history in hours (default 6, max 72)

    Returns:
        Vessel identity, last known position, track history,
        speed/course profile and AIS reporting status.
    """
    hours = min(max(hours, 1), 72)
    vessel = _VESSEL_DB.get(mmsi)

    if not vessel:
        return {
            "status": "NOT_FOUND",
            "mmsi": mmsi,
            "message": f"No AIS record found for MMSI {mmsi}. Possible dark vessel or unregistered craft.",
            "recommendation": "Initiate EO sensor tasking and VHF hail.",
        }

    track = _generate_track(mmsi, hours)
    last_pos = track[-1] if track else {}

    return {
        "status": "FOUND",
        "vessel": vessel,
        "track_summary": {
            "hours_requested": hours,
            "positions_received": len(track),
            "expected_positions": hours * 4,
            "reporting_gap_pct": round((1 - len(track) / (hours * 4)) * 100, 1),
            "last_position": last_pos,
            "avg_speed_kts": round(sum(p["speed_kts"] for p in track) / len(track), 1) if track else 0,
        },
        "track": track[-20:],  # last 20 positions for brevity
        "ais_integrity": "VERIFIED" if vessel["imo"] != "UNVERIFIED" else "UNVERIFIED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 2: classify_vessel
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def classify_vessel(mmsi: str) -> dict:
    """
    Classify vessel type, activity pattern and identity verification.

    Args:
        mmsi: Maritime Mobile Service Identity number

    Returns:
        Vessel classification, activity type, identity confidence score,
        database cross-check results and recommended action.
    """
    vessel = _VESSEL_DB.get(mmsi)

    if not vessel:
        return {
            "mmsi": mmsi,
            "classification": "UNCLASSIFIED",
            "identity_confidence": 0,
            "databases_checked": ["IHS Markit", "Lloyds Register", "ICG VOI DB", "NSC DB"],
            "database_matches": 0,
            "flag_state_verified": False,
            "recommended_action": "INTERCEPT — vessel not found in any registry",
            "alert_level": "RED",
        }

    is_dark = vessel["status"] == "DARK_VESSEL"
    vessel_type = vessel["type"]

    confidence = 95 if not is_dark else 0
    alert = "GREEN" if confidence > 80 else ("AMBER" if confidence > 40 else "RED")

    activity_map = {
        "Cargo": "TRANSIT",
        "Fishing": "FISHING_OPERATIONS",
        "Tanker": "TRANSIT",
        "Unknown": "UNKNOWN — DARK VESSEL",
    }

    return {
        "mmsi": mmsi,
        "vessel_name": vessel["name"],
        "classification": vessel_type.upper(),
        "activity_pattern": activity_map.get(vessel_type, "UNKNOWN"),
        "identity_confidence": confidence,
        "databases_checked": ["IHS Markit", "Lloyds Register", "ICG VOI DB", "NSC DB", "Sanctioned Vessels DB"],
        "database_matches": 4 if not is_dark else 0,
        "flag_state_verified": not is_dark,
        "imo_verified": vessel["imo"] not in ("N/A", "UNVERIFIED"),
        "on_sanctions_list": False,
        "on_voi_watchlist": is_dark,
        "alert_level": alert,
        "recommended_action": (
            "CONTINUE MONITORING" if alert == "GREEN"
            else "HEIGHTEN WATCH + VHF HAIL" if alert == "AMBER"
            else "INTERCEPT AND BOARD"
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 3: flag_anomaly
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def flag_anomaly(mmsi: str, anomaly_type: str = "ALL") -> dict:
    """
    Detect behavioural anomalies for a vessel — loitering, spoofing,
    boundary incursions, suspicious meetings and AIS manipulation.

    Args:
        mmsi: Maritime Mobile Service Identity number
        anomaly_type: LOITERING | SPOOFING | BOUNDARY | MEETING | ALL

    Returns:
        Detected anomalies, confidence scores, supporting evidence
        and recommended ICG response.
    """
    vessel = _VESSEL_DB.get(mmsi)
    is_dark = vessel and vessel["status"] == "DARK_VESSEL"
    is_fishing = vessel and vessel["type"] == "Fishing"

    anomalies = []

    if anomaly_type in ("LOITERING", "ALL") and is_fishing:
        anomalies.append({
            "type": "LOITERING",
            "confidence": 78,
            "description": "Vessel speed < 2 kts for 6+ hours in non-fishing zone",
            "location": "19.45N, 72.38E — 8nm inside IMBL",
            "duration_hrs": 6.5,
            "evidence": ["AIS speed profile", "Course deviation >180 deg", "Position clustering"],
        })

    if anomaly_type in ("SPOOFING", "ALL") and is_dark:
        anomalies.append({
            "type": "AIS_SPOOFING",
            "confidence": 91,
            "description": "AIS transmissions absent for 4+ hours. Vessel visible on radar — identity suppressed.",
            "location": "Last radar contact: 10.22N, 73.15E",
            "duration_hrs": 4.2,
            "evidence": ["Radar track present", "AIS gap >4hrs", "Speed/course inconsistency on resume"],
        })

    if anomaly_type in ("BOUNDARY", "ALL") and (is_dark or is_fishing):
        anomalies.append({
            "type": "EEZ_BOUNDARY_INCURSION",
            "confidence": 85,
            "description": "Foreign-flagged / unverified vessel inside 200nm EEZ without clearance.",
            "location": "9.88N, 72.44E — 15nm inside EEZ boundary",
            "evidence": ["EEZ polygon crossing", "No port clearance on file", "No NOC from DGFT"],
        })

    if anomaly_type in ("MEETING", "ALL") and is_dark:
        anomalies.append({
            "type": "SUSPICIOUS_RENDEZVOUS",
            "confidence": 72,
            "description": "Vessel closed to within 0.3nm of fishing vessel FV SAGAR MITRA at 0230 hrs local.",
            "location": "10.15N, 73.21E",
            "duration_min": 45,
            "evidence": ["AIS proximity alert", "Both vessels stationary", "Night hours", "No radio contact"],
        })

    overall_risk = "RED" if any(a["confidence"] > 85 for a in anomalies) else \
                   "AMBER" if anomalies else "GREEN"

    return {
        "mmsi": mmsi,
        "vessel_name": vessel["name"] if vessel else "UNKNOWN",
        "anomaly_check_type": anomaly_type,
        "anomalies_detected": len(anomalies),
        "overall_risk": overall_risk,
        "anomalies": anomalies,
        "recommended_response": (
            "IMMEDIATE INTERCEPT — multiple high-confidence anomalies" if overall_risk == "RED"
            else "HEIGHTEN MONITORING + VHF CONTACT" if overall_risk == "AMBER"
            else "CONTINUE ROUTINE WATCH"
        ),
        "auto_escalate_to_ops": overall_risk == "RED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 4: get_risk_score
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def get_risk_score(mmsi: str) -> dict:
    """
    Generate dynamic risk score and Vessel of Interest (VOI) ranking
    based on fused AIS, radar, database and behavioural data.

    Args:
        mmsi: Maritime Mobile Service Identity number

    Returns:
        Composite risk score (0-100), VOI ranking, contributing factors
        and recommended ICG action with priority level.
    """
    vessel = _VESSEL_DB.get(mmsi)
    is_dark = vessel and vessel["status"] == "DARK_VESSEL"
    is_fishing = vessel and vessel["type"] == "Fishing"

    # Risk factor scoring
    factors = {
        "AIS_INTEGRITY": 0 if is_dark else (5 if vessel and vessel["imo"] == "N/A" else 0),
        "IDENTITY_VERIFICATION": 40 if is_dark else 0,
        "BEHAVIOURAL_ANOMALY": 25 if is_dark else (15 if is_fishing else 0),
        "DATABASE_MATCH": 0 if (vessel and vessel["status"] == "ACTIVE") else 20,
        "ZONE_COMPLIANCE": 20 if is_dark else (10 if is_fishing else 0),
        "HISTORICAL_PATTERN": 0 if (vessel and vessel["status"] == "ACTIVE") else 15,
    }

    total_score = min(sum(factors.values()), 100)

    voi_rank = "PRIORITY 1 — IMMEDIATE" if total_score > 75 else \
               "PRIORITY 2 — HIGH" if total_score > 50 else \
               "PRIORITY 3 — MEDIUM" if total_score > 25 else \
               "PRIORITY 4 — ROUTINE"

    return {
        "mmsi": mmsi,
        "vessel_name": vessel["name"] if vessel else "UNKNOWN",
        "risk_score": total_score,
        "risk_level": "CRITICAL" if total_score > 75 else
                      "HIGH" if total_score > 50 else
                      "MEDIUM" if total_score > 25 else "LOW",
        "voi_ranking": voi_rank,
        "risk_factors": factors,
        "top_contributing_factor": max(factors, key=factors.get), # type: ignore
        "fused_data_sources": [
            "AIS Track", "Radar", "IHS Markit DB",
            "ICG VOI Watchlist", "NSC Database", "PANS Archive",
        ],
        "recommended_action": (
            "DISPATCH PATROL VESSEL — DO NOT DELAY" if total_score > 75
            else "CONTINUOUS MONITORING + PREPARE INTERCEPT" if total_score > 50
            else "WATCH AND REPORT" if total_score > 25
            else "LOG AND CLEAR"
        ),
        "auto_voi_flag": total_score > 50,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 5: search_pans_data
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def search_pans_data(query: str, area: str = "") -> dict:
    """
    Search PANS (Port and Area Notices) database using natural language query.
    RAG-enabled retrieval over unstructured maritime notices, advisories
    and intelligence bulletins.

    Args:
        query: Natural language search query
              (e.g. "prohibited areas Gulf of Kutch" or "fishing restrictions")
        area: Optional area filter (e.g. "Arabian Sea", "Lakshadweep")

    Returns:
        Matching PANS notices with relevance ranking, area details
        and operational implications.
    """
    query_lower = query.lower()
    area_lower = area.lower()

    results = []
    for pans in _PANS_DB:
        score = 0
        # Simple keyword relevance scoring for demo
        for word in query_lower.split():
            if word in pans["title"].lower(): score += 3
            if word in pans["details"].lower(): score += 2
            if word in pans["area"].lower(): score += 2
        if area_lower and area_lower in pans["area"].lower():
            score += 5
        if score > 0:
            results.append({**pans, "relevance_score": score})

    results.sort(key=lambda x: x["relevance_score"], reverse=True)

    return {
        "query": query,
        "area_filter": area or "ALL",
        "total_pans_in_db": len(_PANS_DB),
        "results_found": len(results),
        "results": results[:5],  # Top 5
        "data_sources": ["ICG PANS Archive", "NLP Marine", "DGLL Notices", "ICG Intel Bulletins"],
        "rag_model": "MCPilot RAG v1.0 — ChromaDB + BGE embeddings",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 6: investigate_vessel
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def investigate_vessel(mmsi: str, reason: str = "ROUTINE") -> dict:
    """
    Full MDA (Maritime Domain Awareness) investigation workflow.
    Fuses AIS track, vessel classification, anomaly detection, risk scoring
    and PANS data into a single structured intelligence report.

    This is the AI-based MDA Assistant described in DISC 14 PS 82 §3.6.

    Args:
        mmsi: Maritime Mobile Service Identity number
        reason: Reason for investigation
                (ROUTINE | SUSPICIOUS_MOVEMENT | BOUNDARY_VIOLATION |
                 DISTRESS | DARK_VESSEL | INTELLIGENCE_INPUT)

    Returns:
        Comprehensive MDA investigation report with evidence,
        risk assessment and recommended ICG action.
    """
    vessel = _VESSEL_DB.get(mmsi)
    track = _generate_track(mmsi, hours=6)
    is_dark = vessel and vessel["status"] == "DARK_VESSEL"

    # Aggregate findings from all tools
    classification = classify_vessel(mmsi)
    risk = get_risk_score(mmsi)
    anomalies = flag_anomaly(mmsi, "ALL")

    # Build factors of suspicion checklist (§3.6 requirement)
    suspicion_factors = []
    if is_dark:
        suspicion_factors.append("Dark vessel — AIS deliberately suppressed")
    if risk["risk_score"] > 50:
        suspicion_factors.append(f"High risk score: {risk['risk_score']}/100")
    if anomalies["anomalies_detected"] > 0:
        for a in anomalies["anomalies"]:
            suspicion_factors.append(f"{a['type']}: {a['description'][:60]}")
    if vessel and vessel.get("flag") == "UNVERIFIED":
        suspicion_factors.append("Flag state not verifiable — not in any registry")
    if track:
        avg_speed = sum(p["speed_kts"] for p in track) / len(track)
        if avg_speed < 2:
            suspicion_factors.append(f"Low average speed {avg_speed:.1f} kts — possible loitering")

    # Recommended actions in priority order
    actions = []
    if risk["risk_score"] > 75:
        actions.append("IMMEDIATE: Dispatch nearest ICG patrol vessel")
        actions.append("IMMEDIATE: Alert MRCC for coordination")
        actions.append("IMMEDIATE: Notify ICG HQ Intelligence Branch")
    elif risk["risk_score"] > 50:
        actions.append("HIGH: Initiate VHF radio contact on Ch 16")
        actions.append("HIGH: Task EO sensor for visual classification")
        actions.append("MEDIUM: Cross-check with NSC and VOI databases")
    else:
        actions.append("ROUTINE: Continue AIS monitoring")
        actions.append("ROUTINE: Log investigation in MDA system")

    return {
        "investigation_id": f"MDA-ICG-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "investigation_reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "vessel_identity": {
            "mmsi": mmsi,
            "name": vessel["name"] if vessel else "UNKNOWN",
            "type": vessel["type"] if vessel else "UNKNOWN",
            "flag": vessel["flag"] if vessel else "UNKNOWN",
            "imo": vessel["imo"] if vessel else "UNKNOWN",
            "call_sign": vessel["call_sign"] if vessel else "UNKNOWN",
        },
        "track_summary": {
            "positions_in_6hrs": len(track),
            "reporting_gap_pct": round((1 - len(track) / 24) * 100, 1),
            "last_position": track[-1] if track else None,
            "avg_speed_kts": round(sum(p["speed_kts"] for p in track) / len(track), 1) if track else 0,
        },
        "risk_assessment": {
            "score": risk["risk_score"],
            "level": risk["risk_level"],
            "voi_ranking": risk["voi_ranking"],
        },
        "anomalies": anomalies["anomalies"],
        "factors_of_suspicion": suspicion_factors,
        "classification": classification["classification"],
        "alert_level": classification["alert_level"],
        "recommended_actions": actions,
        "auto_escalated": risk["risk_score"] > 75,
        "investigation_complete": True,
        "reporting_officer": "MCPilot MDA Assistant v1.0",
    }


if __name__ == "__main__":
    mcp.run()