#!/usr/bin/env python3
"""
Task: Open Workspace Folder in Visual Studio Code

Description:
1. Reopens and activates Visual Studio Code using osascript (reopen + activate).
2. Uses full DFS accessibility tree state extraction (utils.dfs_tree.capture_full_dfs_tree) for baseline S0.
3. Dispatches Cmd+O to trigger the native macOS file picker sheet.
4. Invokes 'Go to the folder' via Cmd+Shift+G and enters the absolute target directory path.
5. Confirms folder selection via Return, opening the requested workspace in VS Code.
6. Logs all state transition diffs (+/- git style) to tasks/logs/open_vscode_folder_<timestamp>.diff.log.

Usage:
  python3 tasks/open_vscode_folder.py
  python3 tasks/open_vscode_folder.py "/Users/harshit/Desktop/YC/LLM_OS"
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
    folder_name = os.path.basename(target_folder)
    
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(logs_dir, f"open_vscode_folder_{timestamp}.diff.log")
    
    logger = HarnessLogger(
        log_path=log_path,
        task_name=f"Open VS Code Folder ('{folder_name}')",
        strip_ephemeral=True,
        context_lines=3
    )
    
    # STEP 0: Reopen and Activate VS Code
    print("[1/5] Activating Visual Studio Code...")
    subprocess.run(["osascript", "-e", 'tell application "Visual Studio Code" to reopen', "-e", 'tell application "Visual Studio Code" to activate'], check=True)
    time.sleep(1.5)
    
    # Baseline Capture
    s0 = capture_full_dfs_tree(app_name="Visual Studio Code")
    if not s0.get("ok"):
        s0 = capture_full_dfs_tree()
    logger.log_initial_state(s0.get("data", {}).get("tree", {}), description="VS Code Initial State Baseline")
    
    # STEP 1: Open Dialog
    print("[2/5] Triggering Open Dialog (Cmd+O)...")
    subprocess.run(["osascript", "-e", 'tell application "Visual Studio Code" to activate'], check=True)
    time.sleep(0.3)
    run_agent_cmd(["press", "cmd+o"])
    
    # Wait for Open Sheet
    s1 = None
    for _ in range(10):
        time.sleep(1)
        s_curr = capture_full_dfs_tree(app_name="Visual Studio Code")
        if not s_curr.get("ok"):
            s_curr = capture_full_dfs_tree()
        tree = s_curr.get("data", {}).get("tree", {})
        if find_node(tree, role="sheet") or find_node(tree, native_id="open-panel"):
            s1 = s_curr
            break
            
    if not s1:
        s1 = capture_full_dfs_tree()
        
    logger.log_action("Trigger Open Dialog", action_details={"keys": "cmd+o"}, new_state=s1.get("data", {}).get("tree", {}), description="Opened file picker sheet")
    
    # STEP 2: Go To Folder
    print("[3/5] Navigating to path input (Cmd+Shift+G)...")
    subprocess.run(["osascript", "-e", 'tell application "Visual Studio Code" to activate'], check=True)
    time.sleep(0.3)
    run_agent_cmd(["press", "cmd+shift+g"])
    time.sleep(1)
    
    s2 = capture_full_dfs_tree(app_name="Visual Studio Code")
    logger.log_action("Trigger Go To Folder", action_details={"keys": "cmd+shift+g"}, new_state=s2.get("data", {}).get("tree", {}))
    
    # STEP 3: Enter Path
    print(f"[4/5] Entering target path '{target_folder}'...")
    run_agent_cmd(["clipboard-set", target_folder])
    subprocess.run(["osascript", "-e", 'tell application "Visual Studio Code" to activate'], check=True)
    time.sleep(0.3)
    run_agent_cmd(["press", "cmd+v"])
    time.sleep(0.5)
    run_agent_cmd(["press", "return"])
    time.sleep(1.5)
    
    s3 = capture_full_dfs_tree(app_name="Visual Studio Code")
    logger.log_action("Navigate to Target Path", action_details={"path": target_folder}, new_state=s3.get("data", {}).get("tree", {}))
    
    # STEP 4: Confirm Opening
    print("[5/5] Confirming folder selection...")
    subprocess.run(["osascript", "-e", 'tell application "Visual Studio Code" to activate'], check=True)
    time.sleep(0.3)
    run_agent_cmd(["press", "return"])
    time.sleep(3)
    
    # Verification
    s4 = capture_full_dfs_tree(app_name="Visual Studio Code")
    tree4 = s4.get("data", {}).get("tree", {})
    matched = find_node(tree4, name_contains=folder_name)
    success = matched is not None or folder_name in str(s4)
    
    logger.log_action("Confirm Open Folder", action_details={"confirmed": True, "target": folder_name}, new_state=tree4)
    logger.finalize(success=success, notes=f"VS Code opened folder '{target_folder}'. Match verified: {success}")
    print(f"\nTask Finished! Execution diff log saved to: {log_path}")

if __name__ == "__main__":
    main()
