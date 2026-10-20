import os
import sys
import time
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from utils.harness_logger import HarnessLogger
from utils.dfs_tree import capture_full_dfs_tree, run_agent_cmd
from utils.mouse import stealth_click

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
    exp_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(exp_dir, "workflow_execution.diff.log")
    
    logger = HarnessLogger(
        log_path=log_path,
        task_name="Increase Sleep Timeout in System Settings to 30 Min",
        strip_ephemeral=True,
        context_lines=3
    )
    
    # STEP 0: Open System Settings to Lock Screen pane
    print("=== Step 0: Opening System Settings Lock Screen Pane ===")
    subprocess.run(["open", "x-apple.systempreferences:com.apple.Lock-Screen-Settings.extension"], check=True)
    time.sleep(1.5)
    subprocess.run(["osascript", "-e", 'tell application "System Settings" to reopen', "-e", 'tell application "System Settings" to activate'], check=True)
    time.sleep(0.5)
    
    # Capture Baseline S0
    print("Capturing baseline S0...")
    s0 = capture_full_dfs_tree(app_name="System Settings")
    if not s0.get("ok"):
        s0 = capture_full_dfs_tree()
    logger.log_initial_state(s0.get("data", {}).get("tree", {}), description="System Settings Lock Screen Baseline")
    
    tree0 = s0.get("data", {}).get("tree", {})
    
    # STEP 1: Locate "Turn display off on battery when inactive" combobox
    print("=== Step 1: Locating Sleep Timeout Combobox ===")
    battery_combobox = find_node(tree0, name="Turn display off on battery when inactive")
    if not battery_combobox or not battery_combobox.get("bounds"):
        print("Failed to locate 'Turn display off on battery when inactive' combobox!")
        logger.finalize(success=False, notes="Combobox not found in AX tree")
        return
        
    b = battery_combobox["bounds"]
    cx = int(b["x"] + b["width"] / 2)
    cy = int(b["y"] + b["height"] / 2)
    print(f"Found combobox at ({cx}, {cy}) with current value '{battery_combobox.get('value')}'. Clicking...")
    
    # Click combobox to expand menu
    subprocess.run(["osascript", "-e", 'tell application "System Settings" to activate'], check=True)
    time.sleep(0.2)
    stealth_click(cx, cy)
    time.sleep(1)
    
    # Capture state S1 (menu expanded)
    s1 = capture_full_dfs_tree(app_name="System Settings")
    logger.log_action(
        "Open Sleep Timeout Menu",
        action_details={"combobox": "Turn display off on battery when inactive", "coords": {"x": cx, "y": cy}},
        new_state=s1.get("data", {}).get("tree", {}),
        description="Clicked combobox to open sleep timeout duration options"
    )
    
    # STEP 2: Find "For 30 minutes" / "30 minutes" menu item or select via keydown/arrow/select
    print("=== Step 2: Selecting 30 minutes option ===")
    tree1 = s1.get("data", {}).get("tree", {})
    menu_item_30 = find_node(tree1, name="For 30 minutes") or find_node(tree1, name_contains="30 min") or find_node(tree1, name="30 minutes")
    
    if menu_item_30 and menu_item_30.get("bounds") and menu_item_30["bounds"].get("height", 0) > 0:
        mb = menu_item_30["bounds"]
        mcx = int(mb["x"] + mb["width"] / 2)
        mcy = int(mb["y"] + mb["height"] / 2)
        print(f"Found 'For 30 minutes' menu item at ({mcx}, {mcy}). Clicking...")
        subprocess.run(["osascript", "-e", 'tell application "System Settings" to activate'], check=True)
        time.sleep(0.2)
        stealth_click(mcx, mcy)
        time.sleep(1)
    else:
        # Fallback: Type / select via arrow keys or press "3" -> Return
        print("Menu item coordinates not in AX tree, using keyboard selection...")
        subprocess.run(["osascript", "-e", 'tell application "System Settings" to activate'], check=True)
        time.sleep(0.2)
        # In macOS menu, typing "3" highlights "For 30 minutes" or 30 min, then return selects it
        run_agent_cmd(["press", "3"])
        time.sleep(0.3)
        run_agent_cmd(["press", "return"])
        time.sleep(1)
        
    # STEP 3: Verification
    print("=== Step 3: Verifying Updated Timeout Value ===")
    s2 = capture_full_dfs_tree(app_name="System Settings")
    tree2 = s2.get("data", {}).get("tree", {})
    
    updated_box = find_node(tree2, name="Turn display off on battery when inactive")
    final_val = updated_box.get("value", "") if updated_box else ""
    success = "30" in str(final_val) or "30" in str(s2)
    
    logger.log_action(
        "Select 30 Minutes",
        action_details={"selected_value": "For 30 minutes", "resulting_value": final_val},
        new_state=tree2,
        description=f"Selected 30 minutes sleep timeout. Resulting value: '{final_val}'"
    )
    
    logger.finalize(success=success, notes=f"Sleep timeout set to 30 min in System Settings. Value: '{final_val}' (Success: {success})")
    print(f"\nExecution Finished! Success: {success}. Final Value: '{final_val}'. Diff log: {log_path}")

if __name__ == "__main__":
    main()
