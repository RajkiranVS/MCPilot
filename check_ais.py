from dotenv import load_dotenv
load_dotenv()
import sys, time
sys.path.insert(0, '.')
print('Waiting 10s for AIS stream...')
time.sleep(10)
from app.mcp.servers.maritime_server import _live_vessels
print('Live vessels:', len(_live_vessels))
for mmsi, v in list(_live_vessels.items())[:5]:
    name = v.get('name', '?')
    lat = v.get('lat', 0)
    lon = v.get('lon', 0)
    spd = v.get('speed', 0)
    print(f'  {mmsi} | {name} | {lat}N {lon}E | {spd}kts')
