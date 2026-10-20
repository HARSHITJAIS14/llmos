import json
import subprocess
import time
import os

AGENT = '/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js'
EXP_DIR = os.path.abspath(os.path.dirname(__file__))

def run_cmd(args):
    res = subprocess.run([AGENT] + args, capture_output=True, text=True)
    try:
        return json.loads(res.stdout)
    except Exception as e:
        return {"ok": False, "raw": res.stdout, "error": str(e)}

print("=== STEP 1: Activate Calendar ===")
subprocess.run(["osascript", "-e", 'tell application "Calendar" to activate'], check=True)
time.sleep(1)

print("=== STEP 2: Press Cmd+N ===")
subprocess.run(["osascript", "-e", 'tell application "Calendar" to activate'], check=True)
run_cmd(["press", "cmd+n"])
time.sleep(1.5)

print("=== STEP 3: Test snapshot surfaces ===")
for surface in ["focused", "popover", "sheet", "window"]:
    print(f"\n--- Testing surface: {surface} ---")
    snap = run_cmd(["snapshot", "--surface", surface, "-i", "--include-bounds"])
    if snap.get("ok"):
        tree = snap.get("data", {}).get("tree", {})
        print(f"✅ Success on surface '{surface}'! Root role: {tree.get('role')} | Name: '{tree.get('name')}'")
        filepath = os.path.join(EXP_DIR, f"calendar_surface_{surface}.json")
        with open(filepath, "w") as f:
            json.dump(snap, f, indent=2)
        print(f"Saved: {filepath}")
    else:
        print(f"❌ Failed on surface '{surface}': {snap.get('error')}")

print("\n=== STEP 4: Test typing directly vs paste ===")
# Set clipboard
run_cmd(["clipboard-set", "visit Hc at 3 pm"])
subprocess.run(["osascript", "-e", 'tell application "Calendar" to activate'], check=True)
time.sleep(0.3)
run_cmd(["press", "cmd+v"])
time.sleep(1)

print("Pressing Return (1st)...")
subprocess.run(["osascript", "-e", 'tell application "Calendar" to activate'], check=True)
run_cmd(["press", "return"])
time.sleep(1)

print("Pressing Return (2nd)...")
subprocess.run(["osascript", "-e", 'tell application "Calendar" to activate'], check=True)
run_cmd(["press", "return"])
time.sleep(1)

print("=== Done ===")
