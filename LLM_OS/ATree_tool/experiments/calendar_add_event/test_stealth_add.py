import json
import subprocess
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from utils.mouse import stealth_click

AGENT = '/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js'
EXP_DIR = os.path.abspath(os.path.dirname(__file__))

def run_cmd(args):
    res = subprocess.run([AGENT] + args, capture_output=True, text=True)
    try:
        return json.loads(res.stdout)
    except Exception as e:
        return {"ok": False, "raw": res.stdout, "error": str(e)}

def save_pretty(filename, data):
    path = os.path.join(EXP_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved: {path}")

print("=== STEP 1: Activate Calendar & Press Cmd+N ===")
subprocess.run(["osascript", "-e", 'tell application "Calendar" to activate'], check=True)
time.sleep(1)
run_cmd(["press", "cmd+n"])
time.sleep(1.5)

print("\n=== STEP 2: Snapshot popover to locate QuickEventCell bounds ===")
snap = run_cmd(["snapshot", "--surface", "popover", "-i", "--include-bounds"])
if not snap.get("ok"):
    print("Failed to snapshot popover:", snap.get("error"))
    sys.exit(1)

save_pretty("calendar_popover_before_click.json", snap)

tree = snap.get("data", {}).get("tree", {})

# Helper to find QuickEventCell
cell_node = None
def find_cell(n):
    global cell_node
    if cell_node: return
    if n.get("native_id", {}).get("value") == "QuickEventCell" or "quick event" in str(n.get("name")).lower():
        cell_node = n
        return
    for c in n.get("children", []):
        find_cell(c)

find_cell(tree)

if not cell_node or not cell_node.get("bounds"):
    print("Could not find QuickEventCell textfield in popover tree.")
    sys.exit(1)

b = cell_node["bounds"]
cx = int(b["x"] + b["width"] / 2)
cy = int(b["y"] + b["height"] / 2)
print(f"Found QuickEventCell! Bounds: {b} -> Center: ({cx}, {cy})")

print("\n=== STEP 3: Executing STEALTH CLICK on QuickEventCell ===")
subprocess.run(["osascript", "-e", 'tell application "Calendar" to activate'], check=True)
time.sleep(0.3)
click_ok = stealth_click(cx, cy)
print(f"Stealth click status: {click_ok}")
time.sleep(0.5)

print("\n=== STEP 4: Pasting Event Text 'visit Hc at 3 pm' ===")
run_cmd(["clipboard-set", "visit Hc at 3 pm"])
subprocess.run(["osascript", "-e", 'tell application "Calendar" to activate'], check=True)
time.sleep(0.3)
run_cmd(["press", "cmd+v"])
time.sleep(0.5)

print("\n=== STEP 5: Confirming event with Return key ===")
subprocess.run(["osascript", "-e", 'tell application "Calendar" to activate'], check=True)
time.sleep(0.3)
run_cmd(["press", "return"])
time.sleep(1.5)

print("\n=== STEP 6: Verifying post-click state ===")
post_snap = run_cmd(["snapshot", "--surface", "popover", "-i", "--include-bounds"])
save_pretty("calendar_popover_after_confirm.json", post_snap)

print("\n=== Done ===")
