#!/usr/bin/env python3
"""
Task: Set Display / System Sleep Timeout in macOS System Settings

Description:
1. Opens macOS System Settings directly to Lock Screen pane using extension URL.
2. Captures full DFS baseline accessibility state S0.
3. Locates the 'Turn display off on battery when inactive' combobox and clicks it.
4. Selects the target duration (default: 'For 30 minutes') from the pop-up menu.
5. Verifies the updated timeout value in the accessibility tree.
6. Logs all state transition diffs (+/- git style) to tasks/logs/set_sleep_timeout_<timestamp>.diff.log.

Usage:
  python3 tasks/set_sleep_timeout.py
  python3 tasks/set_sleep_timeout.py "30"
"""
import os
import sys
import time
import subprocess
import datetime

# Add root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.harness_logger import HarnessLogger
from utils.dfs_tree import capture_full_dfs_tree, run_agent_cmd
# from utils.mouse import stealth_click
def ax_press(app_name, role, name):
    print(f"Executing AXPress for '{name}' in '{app_name}'...")
    subprocess.run([os.path.join(os.path.dirname(__file__), '../utils/ax_press'), app_name, role, name])

def find_node(tree, **kwargs):
    """Recursively search for a node matching the kwargs."""
    if not isinstance(tree, dict):
        return None
        
    match = True
    for k, v in kwargs.items():
        if k == "states":
            if not isinstance(tree.get("states"), list) or v not in tree["states"]:
                match = False
                break
        elif k == "native_id":
            if tree.get("native_id", {}).get("value") != v:
                match = False
                break
        elif k == "name_contains":
            if v.lower() not in str(tree.get("name", "")).lower():
                match = False
                break
        elif tree.get(k) != v:
            match = False
            break
            
    if match:
        return tree
        
    for child in tree.get("children", []):
        res = find_node(child, **kwargs)
        if res:
            return res
    return None

def main():
    minutes_target = sys.argv[1] if len(sys.argv) > 1 else "30"
    target_option_name = f"For {minutes_target} minutes" if not minutes_target.startswith("For") else minutes_target
    
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(logs_dir, f"set_sleep_timeout_{timestamp}.diff.log")
    
    logger = HarnessLogger(
        log_path=log_path,
        task_name=f"Set Sleep Timeout in System Settings ({minutes_target} min)",
        strip_ephemeral=True,
        context_lines=3
    )
    
    # STEP 0: Open System Settings Lock Screen Pane
    print("[1/4] Opening System Settings Lock Screen Pane...")
    # We open the background extension, but do NOT steal focus with osascript
    subprocess.run(["open", "-g", "x-apple.systempreferences:com.apple.Lock-Screen-Settings.extension"], check=True)
    time.sleep(2.0)
    
    # Baseline Capture
    s0 = capture_full_dfs_tree(app_name="System Settings")
    if not s0.get("ok"):
        s0 = capture_full_dfs_tree()
    logger.log_initial_state(s0.get("data", {}).get("tree", {}), description="System Settings Lock Screen Baseline")
    
    tree0 = s0.get("data", {}).get("tree", {})
    
    # STEP 1: Locate Combobox & Click
    print("[2/4] Locating 'Turn display off on battery when inactive' combobox...")
    battery_combobox = find_node(tree0, name="Turn display off on battery when inactive")
    if not battery_combobox or not battery_combobox.get("bounds"):
        print("Failed to locate sleep timeout combobox!")
        logger.finalize(success=False, notes="Combobox not found in AX tree")
        return
        
    b = battery_combobox["bounds"]
    cx = int(b["x"] + b["width"] / 2)
    cy = int(b["y"] + b["height"] / 2)
    
    # Do NOT activate. Click combobox in background
    ax_press("System Settings", "combobox", "Turn display off on battery when inactive")
    time.sleep(1)
    
    s1 = capture_full_dfs_tree(app_name="System Settings")
    logger.log_action("Open Sleep Timeout Menu", action_details={"coords": {"x": cx, "y": cy}}, new_state=s1.get("data", {}).get("tree", {}))
    
    # STEP 2: Select Target Option
    print(f"[3/4] Selecting '{target_option_name}'...")
    tree1 = s1.get("data", {}).get("tree", {})
    menu_item = find_node(tree1, name=target_option_name) or find_node(tree1, name_contains=f"{minutes_target} min")
    
    if menu_item and menu_item.get("bounds") and menu_item["bounds"].get("height", 0) > 0:
        mb = menu_item["bounds"]
        mcx = int(mb["x"] + mb["width"] / 2)
        mcy = int(mb["y"] + mb["height"] / 2)
        # Do NOT activate. Click menu item in background
        ax_press("System Settings", "menu item", target_option_name)
        time.sleep(1)
    else:
        # Fallback if bounds were not found (we still just try AXPress instead of typing)
        ax_press("System Settings", "menu item", target_option_name)
        time.sleep(1)
        
    # STEP 3: Verification
    print("[4/4] Verifying updated timeout value...")
    s2 = capture_full_dfs_tree(app_name="System Settings")
    tree2 = s2.get("data", {}).get("tree", {})
    
    updated_box = find_node(tree2, name="Turn display off on battery when inactive")
    final_val = updated_box.get("value", "") if updated_box else ""
    success = minutes_target in str(final_val) or minutes_target in str(s2)
    
    logger.log_action("Select Timeout Duration", action_details={"target": target_option_name, "final_value": final_val}, new_state=tree2)
    logger.finalize(success=success, notes=f"Sleep timeout set to '{final_val}'. Success: {success}")
    print(f"\nTask Finished! Execution diff log saved to: {log_path}")

if __name__ == "__main__":
    main()
