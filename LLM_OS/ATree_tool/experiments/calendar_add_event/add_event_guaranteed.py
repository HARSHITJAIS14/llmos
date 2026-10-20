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
subprocess.run(["osascript", "-e", 'tell application "Calendar" to reopen', "-e", 'tell application "Calendar" to activate'], check=True)
time.sleep(1)
run_cmd(["press", "cmd+n"])
time.sleep(1.5)

print("\n=== STEP 2: Snapshot Popover to check tabs (Event vs Reminder) ===")
snap1 = run_cmd(["snapshot", "--surface", "popover", "-i", "--include-bounds"])
save_pretty("calendar_guaranteed_step2.json", snap1)

tree1 = snap1.get("data", {}).get("tree", {})

# Helper to find node by native_id or name
def find_node(n, predicate):
    if predicate(n):
        return n
    for c in n.get("children", []):
        found = find_node(c, predicate)
        if found: return found
    return None

new_event_btn = find_node(tree1, lambda n: n.get("native_id", {}).get("value") == "QuickEventNewEventButton" or n.get("name") == "New Event")

if new_event_btn and new_event_btn.get("bounds"):
    b = new_event_btn["bounds"]
    cx = int(b["x"] + b["width"] / 2)
    cy = int(b["y"] + b["height"] / 2)
    print(f"Selecting 'New Event' tab at ({cx}, {cy})...")
    subprocess.run(["osascript", "-e", 'tell application "Calendar" to reopen', "-e", 'tell application "Calendar" to activate'], check=True)
    time.sleep(0.2)
    stealth_click(cx, cy)
    time.sleep(0.5)

quick_cell = find_node(tree1, lambda n: n.get("native_id", {}).get("value") == "QuickEventCell" or "quick event" in str(n.get("name")).lower())

if quick_cell and quick_cell.get("bounds"):
    b = quick_cell["bounds"]
    cx = int(b["x"] + b["width"] / 2)
    cy = int(b["y"] + b["height"] / 2)
    print(f"Focusing QuickEventCell textfield at ({cx}, {cy})...")
    subprocess.run(["osascript", "-e", 'tell application "Calendar" to reopen', "-e", 'tell application "Calendar" to activate'], check=True)
    time.sleep(0.2)
    stealth_click(cx, cy)
    time.sleep(0.5)

print("\n=== STEP 3: Pasting 'visit Hc at 3 pm' ===")
run_cmd(["clipboard-set", "visit Hc at 3 pm"])
subprocess.run(["osascript", "-e", 'tell application "Calendar" to reopen', "-e", 'tell application "Calendar" to activate'], check=True)
time.sleep(0.3)
run_cmd(["press", "cmd+v"])
time.sleep(0.5)

print("\n=== STEP 4: Submitting Quick Event (Return) ===")
subprocess.run(["osascript", "-e", 'tell application "Calendar" to reopen', "-e", 'tell application "Calendar" to activate'], check=True)
time.sleep(0.3)
run_cmd(["press", "return"])
time.sleep(1.5)

print("\n=== STEP 5: Checking Inspector Popover State ===")
snap2 = run_cmd(["snapshot", "--surface", "popover", "-i", "--include-bounds"])
save_pretty("calendar_guaranteed_step5.json", snap2)

tree2 = snap2.get("data", {}).get("tree", {})

# Check if 'Event' radiobutton is present in inspector and needs clicking
event_radio = find_node(tree2, lambda n: n.get("role") == "radiobutton" and n.get("name") == "Event")

if event_radio and event_radio.get("bounds"):
    b = event_radio["bounds"]
    cx = int(b["x"] + b["width"] / 2)
    cy = int(b["y"] + b["height"] / 2)
    print(f"Switching Inspector to 'Event' radiobutton at ({cx}, {cy})...")
    subprocess.run(["osascript", "-e", 'tell application "Calendar" to reopen', "-e", 'tell application "Calendar" to activate'], check=True)
    time.sleep(0.2)
    stealth_click(cx, cy)
    time.sleep(0.8)

# Finalize / Save event by pressing Return
print("\n=== STEP 6: Finalizing Event (Return) ===")
subprocess.run(["osascript", "-e", 'tell application "Calendar" to reopen', "-e", 'tell application "Calendar" to activate'], check=True)
time.sleep(0.3)
run_cmd(["press", "return"])
time.sleep(1.5)

print("\n=== STEP 7: Final Verification ===")
snap3 = run_cmd(["snapshot", "--surface", "popover", "-i", "--include-bounds"])
save_pretty("calendar_guaranteed_final.json", snap3)

print("=== Execution Finished ===")
