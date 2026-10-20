import json
import subprocess

AGENT = '/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js'

res = subprocess.run([AGENT, "list-windows", "--app", "Calendar"], capture_output=True, text=True)
try:
    data = json.loads(res.stdout)
    windows = data.get("data", [])
    print(f"Found {len(windows)} Calendar windows.")
    for w in windows:
        wid = w["id"]
        print(f"\nTesting Window ID: {wid} (bounds: {w.get('bounds')})...")
        snap = subprocess.run([AGENT, "snapshot", "--window-id", wid], capture_output=True, text=True)
        try:
            s_data = json.loads(snap.stdout)
            if s_data.get("ok"):
                print(f"✅ SUCCESS on {wid}! Root role: {s_data.get('data', {}).get('tree', {}).get('role')}")
            else:
                print(f"❌ Failed on {wid}: {s_data.get('error', {}).get('code')} - {s_data.get('error', {}).get('message')}")
        except Exception as e:
            print(f"Parse error: {e}")
except Exception as e:
    print(f"List windows error: {e}")
