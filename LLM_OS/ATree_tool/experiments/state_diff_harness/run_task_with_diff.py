"""
Harness Execution Script with Full DFS Tree State Diff Logging.

Demonstrates executing a multi-step LLM_OS workflow (Calendar Add Event)
where EVERY step captures a 100% complete DFS tree (expanding all truncated web/container nodes)
and logs state diffs (+/- lines, git style) in a single comprehensible execution log file.

Usage:
  python3 experiments/state_diff_harness/run_task_with_diff.py "Team Standup at 4 pm"
"""
import json
import subprocess
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from utils.mouse import stealth_click
from utils.harness_logger import HarnessLogger
from utils.dfs_tree import capture_full_dfs_tree, run_agent_cmd

EXP_DIR = os.path.dirname(__file__)

def find_node(n, predicate):
    if not isinstance(n, dict):
        return None
    if predicate(n):
        return n
    for c in n.get("children", []):
        found = find_node(c, predicate)
        if found: return found
    return None

def main():
    event_text = sys.argv[1] if len(sys.argv) > 1 else "Sync meeting at 5 pm"
    log_path = os.path.join(EXP_DIR, "workflow_execution.diff.log")
    
    logger = HarnessLogger(
        log_path=log_path,
        task_name=f"Add Calendar Event ('{event_text}')",
        strip_ephemeral=True,
        context_lines=3
    )

    print(f"=== Starting Task: Add Calendar Event ('{event_text}') ===")
    print(f"Logging full DFS workflow diffs to: {log_path}\n")

    # STEP 0: Activate Calendar & Capture Baseline Full DFS Tree
    print("[Harness] Step 0: Activating Calendar & Capturing Baseline Full DFS Tree...")
    subprocess.run(["osascript", "-e", 'tell application "Calendar" to reopen', "-e", 'tell application "Calendar" to activate'], check=True)
    time.sleep(1)
    snap0 = capture_full_dfs_tree(app_name="Calendar")
    logger.log_initial_state(snap0, description="Initial Full DFS Baseline")

    # STEP 1: Press Cmd+N to open Quick Event popover
    print("[Harness] Step 1: Triggering Quick Event popover (Cmd+N)...")
    subprocess.run(["osascript", "-e", 'tell application "Calendar" to reopen', "-e", 'tell application "Calendar" to activate'], check=True)
    time.sleep(0.2)
    run_agent_cmd(["press", "cmd+n"])
    time.sleep(1.5)
    
    snap1 = capture_full_dfs_tree(app_name="Calendar")
    logger.log_action(
        action_name="press_shortcut",
        action_details={"shortcut": "cmd+n", "target": "Calendar"},
        new_state=snap1,
        description="Opened Quick Event creation popover"
    )

    # STEP 2: Select 'New Event' tab and focus input cell
    print("[Harness] Step 2: Ensuring 'New Event' tab and focusing input...")
    tree1 = snap1.get("data", {}).get("tree", {})
    new_event_btn = find_node(tree1, lambda n: n.get("native_id", {}).get("value") == "QuickEventNewEventButton" or n.get("name") == "New Event")

    if new_event_btn and new_event_btn.get("bounds"):
        b = new_event_btn["bounds"]
        cx, cy = int(b["x"] + b["width"] / 2), int(b["y"] + b["height"] / 2)
        subprocess.run(["osascript", "-e", 'tell application "Calendar" to reopen', "-e", 'tell application "Calendar" to activate'], check=True)
        time.sleep(0.2)
        stealth_click(cx, cy)
        time.sleep(0.5)

    quick_cell = find_node(tree1, lambda n: n.get("native_id", {}).get("value") == "QuickEventCell" or "quick event" in str(n.get("name")).lower())
    if quick_cell and quick_cell.get("bounds"):
        b = quick_cell["bounds"]
        cx, cy = int(b["x"] + b["width"] / 2), int(b["y"] + b["height"] / 2)
        subprocess.run(["osascript", "-e", 'tell application "Calendar" to reopen', "-e", 'tell application "Calendar" to activate'], check=True)
        time.sleep(0.2)
        stealth_click(cx, cy)
        time.sleep(0.5)

    # STEP 3: Set clipboard & Paste event text
    print(f"[Harness] Step 3: Setting clipboard and pasting event text ('{event_text}')...")
    run_agent_cmd(["clipboard-set", event_text])
    subprocess.run(["osascript", "-e", 'tell application "Calendar" to reopen', "-e", 'tell application "Calendar" to activate'], check=True)
    time.sleep(0.3)
    run_agent_cmd(["press", "cmd+v"])
    time.sleep(0.5)

    snap2 = capture_full_dfs_tree(app_name="Calendar")
    logger.log_action(
        action_name="paste_text",
        action_details={"text": event_text, "shortcut": "cmd+v"},
        new_state=snap2,
        description="Pasted event details into QuickEventCell"
    )

    # STEP 4: Submit Quick Event popover (Return key)
    print("[Harness] Step 4: Submitting Quick Event (Return)...")
    subprocess.run(["osascript", "-e", 'tell application "Calendar" to reopen', "-e", 'tell application "Calendar" to activate'], check=True)
    time.sleep(0.3)
    run_agent_cmd(["press", "return"])
    time.sleep(1.5)

    snap3 = capture_full_dfs_tree(app_name="Calendar")
    logger.log_action(
        action_name="press_key",
        action_details={"key": "return"},
        new_state=snap3,
        description="Submitted Quick Event cell"
    )

    # STEP 5: Check Inspector and finalize
    tree3 = snap3.get("data", {}).get("tree", {})
    event_radio = find_node(tree3, lambda n: n.get("role") == "radiobutton" and n.get("name") == "Event")
    if event_radio and event_radio.get("bounds"):
        b = event_radio["bounds"]
        cx, cy = int(b["x"] + b["width"] / 2), int(b["y"] + b["height"] / 2)
        subprocess.run(["osascript", "-e", 'tell application "Calendar" to reopen', "-e", 'tell application "Calendar" to activate'], check=True)
        time.sleep(0.2)
        stealth_click(cx, cy)
        time.sleep(0.8)

    print("[Harness] Step 5: Finalizing event creation (Return)...")
    subprocess.run(["osascript", "-e", 'tell application "Calendar" to reopen', "-e", 'tell application "Calendar" to activate'], check=True)
    time.sleep(0.3)
    run_agent_cmd(["press", "return"])
    time.sleep(1.5)

    snap4 = capture_full_dfs_tree(app_name="Calendar")
    logger.log_action(
        action_name="finalize_event",
        action_details={"key": "return"},
        new_state=snap4,
        description="Finalized event commit"
    )

    logger.finalize(success=True, notes=f"Event '{event_text}' added successfully.")
    print(f"\nTask completed successfully! Diff log saved to: {log_path}")

if __name__ == "__main__":
    main()
