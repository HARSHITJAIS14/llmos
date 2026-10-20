import os
import sys
import time
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from utils.harness_logger import HarnessLogger
from utils.dfs_tree import capture_full_dfs_tree, run_agent_cmd

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
    target_folder = sys.argv[1] if len(sys.argv) > 1 else "/Users/harshit/Desktop/YC/LLM_OS"
    target_folder = os.path.abspath(target_folder)
    
    exp_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(exp_dir, "workflow_execution.diff.log")
    
    logger = HarnessLogger(
        log_path=log_path,
        task_name=f"Open Folder in VS Code ('{os.path.basename(target_folder)}')",
        strip_ephemeral=True,
        context_lines=3
    )
    
    # STEP 0: Context Initialization & App Activation
    print("=== Step 0: Activating Visual Studio Code ===")
    subprocess.run(["osascript", "-e", 'tell application "Visual Studio Code" to reopen', "-e", 'tell application "Visual Studio Code" to activate'], check=True)
    time.sleep(1.5)
    
    # Capture Baseline S0
    print("Capturing baseline S0...")
    s0 = capture_full_dfs_tree(app_name="Visual Studio Code")
    if not s0.get("ok"):
        # Fallback if window title or app filter needs general capture
        s0 = capture_full_dfs_tree()
    logger.log_initial_state(s0.get("data", {}).get("tree", {}), description="VS Code Initial State Baseline")
    
    # STEP 1: Trigger Open Dialog via Cmd+O
    print("=== Step 1: Triggering Open Dialog (Cmd+O) ===")
    subprocess.run(["osascript", "-e", 'tell application "Visual Studio Code" to activate'], check=True)
    time.sleep(0.3)
    run_agent_cmd(["press", "cmd+o"])
    
    # Cognitive Loop: Wait for Open Dialog Sheet
    s1 = None
    for attempt in range(10):
        time.sleep(1)
        print(f"Waiting for open dialog... attempt {attempt + 1}")
        s_curr = capture_full_dfs_tree(app_name="Visual Studio Code")
        if not s_curr.get("ok"):
            s_curr = capture_full_dfs_tree()
        tree = s_curr.get("data", {}).get("tree", {})
        
        # Check for open dialog sheet or open button
        open_sheet = find_node(tree, role="sheet") or find_node(tree, native_id="open-panel") or find_node(tree, name="open") or find_node(tree, name="Open")
        if open_sheet:
            s1 = s_curr
            break
            
    if not s1:
        print("Warning: Open sheet not explicitly detected, continuing with current state...")
        s1 = capture_full_dfs_tree()
        
    logger.log_action("Trigger Open Dialog", action_details={"keys": "cmd+o"}, new_state=s1.get("data", {}).get("tree", {}), description="Triggered Open Folder dialog sheet in VS Code")
    
    # STEP 2: Trigger Go to Folder (Cmd+Shift+G)
    print("=== Step 2: Triggering Go to Folder (Cmd+Shift+G) ===")
    subprocess.run(["osascript", "-e", 'tell application "Visual Studio Code" to activate'], check=True)
    time.sleep(0.3)
    run_agent_cmd(["press", "cmd+shift+g"])
    time.sleep(1)
    
    s2 = capture_full_dfs_tree(app_name="Visual Studio Code")
    logger.log_action("Trigger Go To Folder", action_details={"keys": "cmd+shift+g"}, new_state=s2.get("data", {}).get("tree", {}), description="Opened 'Go to the folder' path input")
    
    # STEP 3: Set Clipboard & Paste Target Folder Path
    print(f"=== Step 3: Entering path '{target_folder}' ===")
    run_agent_cmd(["clipboard-set", target_folder])
    subprocess.run(["osascript", "-e", 'tell application "Visual Studio Code" to activate'], check=True)
    time.sleep(0.3)
    run_agent_cmd(["press", "cmd+v"])
    time.sleep(0.5)
    run_agent_cmd(["press", "return"])
    time.sleep(1.5)
    
    s3 = capture_full_dfs_tree(app_name="Visual Studio Code")
    logger.log_action("Navigate to Target Path", action_details={"path": target_folder, "keys": "cmd+v -> return"}, new_state=s3.get("data", {}).get("tree", {}), description=f"Navigated Open dialog to {target_folder}")
    
    # STEP 4: Confirm Opening the Selected Folder (Return / Open button)
    print("=== Step 4: Confirming Open Folder ===")
    subprocess.run(["osascript", "-e", 'tell application "Visual Studio Code" to activate'], check=True)
    time.sleep(0.3)
    run_agent_cmd(["press", "return"])
    time.sleep(3)
    
    # STEP 5: Verification of VS Code Window with LLM_OS open
    print("=== Step 5: Verifying Workspace State in VS Code ===")
    subprocess.run(["osascript", "-e", 'tell application "Visual Studio Code" to activate'], check=True)
    time.sleep(1)
    s4 = capture_full_dfs_tree(app_name="Visual Studio Code")
    tree4 = s4.get("data", {}).get("tree", {})
    
    folder_name = os.path.basename(target_folder)
    matched = find_node(tree4, name_contains=folder_name)
    success = matched is not None or "LLM_OS" in str(s4)
    
    logger.log_action("Confirm Open Folder", action_details={"confirmed": True, "target": folder_name}, new_state=tree4, description=f"Confirmed opening '{folder_name}' workspace in VS Code")
    
    logger.finalize(success=success, notes=f"VS Code opened folder '{target_folder}'. Match verified: {success}")
    print(f"\nExecution Finished! Success: {success}. Diff log: {log_path}")

if __name__ == "__main__":
    main()
