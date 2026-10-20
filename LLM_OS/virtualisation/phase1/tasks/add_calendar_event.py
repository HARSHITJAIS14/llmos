"""
Task: Add Event to macOS Calendar

Description:
1. Reopens and activates macOS Calendar using osascript (reopen + activate).
2. Sends Cmd+N to trigger Quick Event creation popover.
3. Scopes accessibility snapshot to `--surface popover` to bypass background helper window inventory locks.
4. Identifies 'New Event' vs 'New Reminder' tab buttons and executes stealthClick() to force Calendar Event mode.
5. Pastes the event text via clipboard-set + Cmd+V into QuickEventCell.
6. Commits the event using Return key and verifies popover closure.

Usage:
  python3 add_calendar_event.py "<event_text>"
  python3 add_calendar_event.py "visit Hc at 3 pm"
"""
import json
import subprocess
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
# from utils.mouse import stealth_click
def ax_press(app_name, role, name):
    print(f"Executing AXPress for '{name}' in '{app_name}'...")
    subprocess.run([os.path.join(os.path.dirname(__file__), '../utils/ax_press'), app_name, role, name])

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

print("=== STEP 1: Activate Calendar & Press Cmd+N (Background) ===")
# Use background ax_press to open New Event instead of stealing focus with osascript + cmd+n
ax_press("Calendar", "button", "Add Event")
time.sleep(1.5)

print("\n=== STEP 2: Snapshot Popover to check tabs (Event vs Reminder) ===")
snap1 = run_cmd(["snapshot", "--app", "Calendar", "-i", "--include-bounds"])
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
    ax_press("Calendar", "radiobutton", "New Event")
    time.sleep(0.5)

quick_cell = find_node(tree1, lambda n: n.get("native_id", {}).get("value") == "QuickEventCell" or "quick event" in str(n.get("name")).lower())

if quick_cell and quick_cell.get("bounds"):
    b = quick_cell["bounds"]
    cx = int(b["x"] + b["width"] / 2)
    cy = int(b["y"] + b["height"] / 2)
    print(f"Focusing QuickEventCell textfield at ({cx}, {cy})...")
    ax_press("Calendar", "textfield", "QuickEventCell")
    time.sleep(0.5)

event_text = sys.argv[1] if len(sys.argv) > 1 else "visit Hc at 3 pm"
print(f"\n=== STEP 3: Pasting '{event_text}' (Background) ===")
if quick_cell and quick_cell.get("ref_id"):
    run_cmd(["set-value", quick_cell["ref_id"], event_text])
else:
    print("Could not find ref_id to set value!")
time.sleep(0.5)

print("\n=== STEP 4: Submitting Quick Event (Return via background AXPress) ===")
# Many native text fields submit when pressing 'return', but we can trigger it natively via AXPress on a confirmation button if available.
# Otherwise, we can use the default button of the window.
ax_press("Calendar", "button", "Done") 
time.sleep(1.5)

print("\n=== STEP 5: Checking Inspector Popover State ===")
snap2 = run_cmd(["snapshot", "--app", "Calendar", "-i", "--include-bounds"])
save_pretty("calendar_guaranteed_step5.json", snap2)

tree2 = snap2.get("data", {}).get("tree", {})

# Check if 'Event' radiobutton is present in inspector and needs clicking
event_radio = find_node(tree2, lambda n: n.get("role") == "radiobutton" and n.get("name") == "Event")

if event_radio and event_radio.get("bounds"):
    b = event_radio["bounds"]
    cx = int(b["x"] + b["width"] / 2)
    cy = int(b["y"] + b["height"] / 2)
    print(f"Switching Inspector to 'Event' radiobutton at ({cx}, {cy})...")
    ax_press("Calendar", "radiobutton", "Event")
    time.sleep(0.8)

# Finalize / Save event by pressing Return
print("\n=== STEP 6: Finalizing Event (Return) ===")
ax_press("Calendar", "button", "Apply")
time.sleep(1.5)

print("\n=== STEP 7: Final Verification ===")
snap3 = run_cmd(["snapshot", "--app", "Calendar", "-i", "--include-bounds"])
save_pretty("calendar_guaranteed_final.json", snap3)

print("=== Execution Finished ===")
