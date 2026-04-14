"""
Standalone aisstream.io connection test.
Run: python test_aisstream.py
"""
import asyncio
import json
import os
from dotenv import load_dotenv
import websockets

load_dotenv()

API_KEY = os.environ.get("AISSTREAM_API_KEY", "")
URL     = "wss://stream.aisstream.io/v0/stream"

async def test():
    print(f"API key: {'SET (' + API_KEY[:8] + '...)' if API_KEY else 'MISSING'}")
    print(f"Connecting to {URL}...")

    # Test 1: Global bbox (guaranteed traffic)
    sub_global = {
        "APIKey": API_KEY,
        "BoundingBoxes": [[[-90, -180], [90, 180]]],
        "FilterMessageTypes": ["PositionReport"],
    }

    # Test 2: India bbox as code uses it
    sub_india = {
        "APIKey": API_KEY,
        "BoundingBoxes": [[[6.0, 66.0], [24.0, 98.0]]],
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
    }

    for label, sub in [("GLOBAL", sub_global), ("INDIA", sub_india)]:
        print(f"\n--- Test: {label} bbox ---")
        print(f"Subscription: {json.dumps(sub, indent=2)}")
        try:
            async with websockets.connect(URL, ping_interval=20, open_timeout=10) as ws:
                print("Connected OK")
                await ws.send(json.dumps(sub))
                print("Subscription sent. Waiting 15s for messages...")

                count = 0
                async def read():
                    nonlocal count
                    async for raw in ws:
                        count += 1
                        msg = json.loads(raw)
                        print(f"  MSG #{count} type={msg.get('MessageType','?')} keys={list(msg.keys())}")
                        if count == 1:
                            print(f"  FULL FIRST MSG: {json.dumps(msg, indent=2)[:1000]}")
                        if count >= 3:
                            break

                await asyncio.wait_for(read(), timeout=15)
                print(f"Received {count} messages in 15s")
        except asyncio.TimeoutError:
            print(f"Timeout — {count} messages received in 15s")
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")

asyncio.run(test())
