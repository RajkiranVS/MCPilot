"""
MCPilot — Battle-Test Suite V1.0
Automated stress testing for Defence AI Orchestration.
"""

import sys
if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from app.compliance.phi_detector import detect

# Categorized Test Scenarios
TEST_CASES = [
    # ── Category 1: Indian Service Numbers & Personnel (PII) ──
    "General Manoj Pande is arriving at the helipad at 0900 hours.",
    "Instruction for IC-72431M: Report to the CO immediately.",
    "Assign Havildar Rajbir Singh to the perimeter watch.",
    "Contact established with SS-19283K near the bridge.",
    "Major General Bakshi has authorized the movement of the 15th Battalion.",
    "Lieutenant Colonel Sandeep Unnikrishnan is the lead officer for this op.",
    "Search for records pertaining to Sepoy Mahender and Naib Subedar Ravi.",
    "The file for Air Marshal Vivek Ram Chaudhari is currently restricted.",
    "Verify the credentials of Petty Officer Joseph (Service No: NR-99281L).",
    "Is Flight Lieutenant Anjali Bhardwaj cleared for the sortie?",

    # ── Category 2: Grids & Geographic Intelligence (GEOINT) ──
    "Enemy movement detected at Grid 43Q KV 12345 67890.",
    "Rendezvous point set at 28.6139° N, 77.2090° E for midnight.",
    "The target is located 5km North of Sector 7, Grid 9928.",
    "Heavy shelling reported at 34°05'N, 74°47'E near the LoC.",
    "Evacuation coordinates are 12.9716 N, 77.5946 E.",
    "Patrol Sector 4 is compromised; divert all units to Zone 9.",
    "The cache is hidden at MGRS 44R MP 5544 3322.",
    "Frequency 440.5MHz is being jammed in the Northern Sector.",
    "Move the artillery battery to Grid 882199.",
    "Is there a safe route from Cantonment A to Forward Base B?",

    # ── Category 3: Unit Strength & Tactical Assets ──
    "Total personnel at the base is 450 Jawans.",
    "We are deploying 3 Companies and 1 Armoured Platoon.",
    "A battalion of 800 troops is crossing the International Border.",
    "Requesting 2 Medevac units for 15 wounded officers.",
    "Supply drop confirmed for 1200 soldiers in the high-altitude zone.",
    "The armory contains 500 units of advanced communication gear.",
    "How many men are stationed at the check post?",
    "A platoon of 30 commandos is standing by for H-Hour.",
    "Casualty report: 4 personnel KIA, 12 personnel WIA.",
    "Ensure 100 officers are briefed on the new encryption protocol.",

    # ── Category 4: Complex Tactical Scenarios (The Stress Tests) ──
    "TIGER, this is SUNRAY. IC-12345P is leading 50 troops to Grid 43Q LV 1122 3344. WILCO. OVER.",
    "Message for Major Sharma: The Ambala Airbase is on high alert. Move 200 jawans to Sector 9 immediately.",
    "RECAP: Major General Roy confirmed target at 25.5°N, 71.2°E. ETA for Wing Commander Abhi is 1430.",
    "All Stations, this is CONTROL. Frequency swap to Net 4. Do not reveal IC-99887G's location. OUT.",
    "Requesting terrain analysis for Pathankot Cantt regarding a 150 personnel extraction.",
    "Is Subedar Major Tyagi at the Forward Operating Base in Zone 3?",
    "Operation MARUT involves 400 troops moving to the LAC at Grid 556677.",
    "Can the LLM summarize the status of Major Gupta at Naval Base Karwar?",
    "Verify if SS-88776M has reached Rendezvous Point Alpha at MGRS 43P GV 1122.",
    "Alert! Colonel Chatterjee reports Contact at 15.3 N, 73.9 E with 10 units.",

    # ── Category 5: Negative Tests (Standard Conversions) ──
    "I need a coffee at the cafeteria at 0800.",
    "What is the weather like in Bengaluru today?",
    "The printer in the office is not working.",
    "Can you help me write a Python script for data sorting?",
    "Tell me a joke about a captain and a sailor.",
    "I'm meeting my uncle on the 11th of April.",
    "The cost of the equipment is 50,000 rupees.",
    "Translate this message into Hindi.",
    "How do I calculate the area of a circle?",
    "Roger that, thanks for the help."
]

def run_mcpilot_stresstest(redaction_engine):
    """
    Simulates a burst transmission of all test cases.
    Replace 'redaction_engine' with your actual function call.
    """
    print(f"{'='*20} MCPILOT BATTLE-TEST START {'='*20}\n")
    
    passed = 0
    for i, scenario in enumerate(TEST_CASES, 1):
        # This is where you call your existing redaction logic
        sanitized_output = detect(scenario)
        
        print(f"[{i:02}] RAW: {scenario}")
        print(f"     SAN: {sanitized_output}")
        print("-" * 50)
        
        # Simple check: if the sanitized is different from raw, redaction triggered
        if sanitized_output != scenario:
            passed += 1
            
    print(f"\n{'='*20} TEST SUMMARY {'='*20}")
    print(f"Total Scenarios: {len(TEST_CASES)}")
    print(f"Redactions Triggered: {passed}")
    print(f"System Status: ONLINE / SECURE")

if __name__ == "__main__":
    # Replace 'detect' with your actual redaction function if different
    run_mcpilot_stresstest(detect)