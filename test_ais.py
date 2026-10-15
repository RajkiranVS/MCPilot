"""
MCPilot — AIS Live Feed Diagnostic
Tests aisstream.io connection and checks vessel reception
for Indian coastal waters and surrounding regions.

Run: python test_ais_live.py
"""
import asyncio
import json
import time
from datetime import datetime, timezone

try:
    import websockets
except ImportError:
    print("ERROR: websockets not installed. Run: pip install websockets")
    exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import os

API_KEY = os.environ.get("AISSTREAM_API_KEY", "")
if not API_KEY:
    print("ERROR: AISSTREAM_API_KEY not set in .env")
    exit(1)

print("API Key: set")
print()

# ── Bounding boxes to test ────────────────────────────────────────────────────
BOXES = [
    {
        "name": "Indian Coastal Waters (Target)",
        "bbox": [[6.0, 66.0], [24.0, 98.0]],
        "desc": "Arabian Sea + Bay of Bengal — our operational zone",
    },
    {
        "name": "Gulf of Oman + Arabian Gulf (Nearby)",
        "bbox": [[20.0, 50.0], [30.0, 66.0]],
        "desc": "Busy shipping lane with known AIS coverage",
    },
    {
        "name": "Strait of Malacca (Reference — known good coverage)",
        "bbox": [[1.0, 103.0], [2.0, 104.5]],
        "desc": "Dense traffic zone — should receive data immediately",
    },
]


async def test_bbox(name, bbox, desc, timeout=30):
    """Test a bounding box and return vessel count received."""
    url = "wss://stream.aisstream.io/v0/stream"
    sub = {
        "APIKey":             API_KEY,
        "BoundingBoxes":      [bbox],
        "FilterMessageTypes": ["PositionReport"],
    }

    print(f"{'='*60}")
    print(f"TEST: {name}")
    print(f"DESC: {desc}")
    print(f"BBOX: {bbox[0]} → {bbox[1]}")
    print(f"Listening for {timeout} seconds...")
    print()

    vessels = {}
    msg_count = 0
    start = time.time()

    try:
        async with websockets.connect(url, ping_interval=20, open_timeout=10) as ws:
            await ws.send(json.dumps(sub))
            print("  ✓ Connected and subscribed")

            while time.time() - start < timeout:
                try:
                    remaining = timeout - (time.time() - start)
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(5, remaining))
                    data = json.loads(raw)

                    msg_type = data.get("MessageType", "")
                    if msg_type == "PositionReport":
                        pos  = data.get("Message", {}).get("PositionReport", {})
                        mmsi = str(pos.get("UserID", ""))
                        lat  = pos.get("Latitude", 0)
                        lon  = pos.get("Longitude", 0)
                        spd  = pos.get("Sog", 0)
                        meta = data.get("Metadata", {})
                        name_val = meta.get("ShipName", "UNKNOWN").strip() or "UNKNOWN"

                        if mmsi and mmsi != "0":
                            vessels[mmsi] = {
                                "mmsi": mmsi,
                                "name": name_val,
                                "lat":  round(lat, 4),
                                "lon":  round(lon, 4),
                                "spd":  round(spd, 1),
                            }
                            msg_count += 1
                            elapsed = round(time.time() - start, 1)
                            print(f"  [{elapsed}s] MMSI:{mmsi} | {name_val[:20]:<20} | {lat:.4f}N {lon:.4f}E | {spd:.1f}kts")

                except asyncio.TimeoutError:
                    elapsed = round(time.time() - start, 1)
                    print(f"  [{elapsed}s] No data in last 5s...")
                    continue

    except Exception as e:
        print(f"  ERROR: {e}")

    print()
    print(f"RESULT: {len(vessels)} unique vessels, {msg_count} messages in {timeout}s")
    if vessels:
        print("SAMPLE VESSELS:")
        for v in list(vessels.values())[:5]:
            print(f"  MMSI:{v['mmsi']} | {v['name'][:25]:<25} | {v['lat']}N {v['lon']}E | {v['spd']}kts")
    else:
        print("  NO VESSELS RECEIVED — no AIS receivers in this zone")
    print()
    return vessels


async def main():
    print("MCPilot — AIS Live Feed Diagnostic")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()

    results = {}
    for box in BOXES:
        vessels = await test_bbox(box["name"], box["bbox"], box["desc"], timeout=20)
        results[box["name"]] = len(vessels)
        await asyncio.sleep(2)

    print("=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)
    for name, count in results.items():
        status = "✓ LIVE DATA" if count > 0 else "✗ NO COVERAGE"
        print(f"  {status} | {count:3d} vessels | {name}")

    indian = results.get("Indian Coastal Waters (Target)", 0)
    print()
    if indian > 0:
        print(f"✓ SUCCESS — {indian} vessels detected in Indian coastal waters!")
        print("  Live AIS data is flowing. Update maritime_server.py bbox if needed.")
    else:
        print("✗ No vessels in Indian coastal waters via aisstream.io")
        print("  Reason: Limited terrestrial AIS receiver coverage in Indian waters.")
        print("  Options:")
        print("    1. Use simulated vessels for demo (current approach)")
        print("    2. Integrate MarineTraffic API (has Indian port receivers)")
        print("    3. Wait for ICG CSN data feed (real deployment)")


if __name__ == "__main__":
    asyncio.run(main())