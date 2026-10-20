#!/usr/bin/env python3
"""
Task: Open URL in Brave Browser Private Window

Description:
1. Reopens and activates Brave Browser using osascript (reopen + activate).
2. Uses full DFS accessibility tree state extraction (utils.dfs_tree.capture_full_dfs_tree) for baseline S0.
3. Dispatches Cmd+Shift+N to launch a dedicated Private Window.
4. Focuses the address bar via Cmd+L and pastes the requested URL.
5. Verifies page load and title update in the accessibility tree.
6. Logs all state transition diffs (+/- git style) to tasks/logs/open_brave_private_<timestamp>.diff.log.

Usage:
  python3 tasks/open_brave_private_url.py
  python3 tasks/open_brave_private_url.py "https://www.youtube.com"
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
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com"
    
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(logs_dir, f"open_brave_private_{timestamp}.diff.log")
    
    logger = HarnessLogger(
        log_path=log_path,
        task_name=f"Open Brave Private URL ('{target_url}')",
        strip_ephemeral=True,
        context_lines=3
    )
    
    # STEP 0: Reopen and Activate Brave
    print("[1/4] Activating Brave Browser...")
    subprocess.run(["osascript", "-e", 'tell application "Brave Browser" to reopen', "-e", 'tell application "Brave Browser" to activate'], check=True)
    time.sleep(1.5)
    
    # Baseline Capture
    s0 = capture_full_dfs_tree(app_name="Brave Browser")
    if not s0.get("ok"):
        s0 = capture_full_dfs_tree()
    logger.log_initial_state(s0.get("data", {}).get("tree", {}), description="Brave Browser Baseline State")
    
    # STEP 1: Launch Private Window
    print("[2/4] Opening Private Window (Cmd+Shift+N)...")
    subprocess.run(["osascript", "-e", 'tell application "Brave Browser" to activate'], check=True)
    time.sleep(0.3)
    run_agent_cmd(["press", "cmd+shift+n"])
    time.sleep(1.5)
    
    s1 = capture_full_dfs_tree(app_name="Brave Browser")
    logger.log_action("Open Private Window", action_details={"keys": "cmd+shift+n"}, new_state=s1.get("data", {}).get("tree", {}))
    
    # STEP 2: Navigate to URL
    print(f"[3/4] Navigating to '{target_url}' (Cmd+L -> Cmd+V -> Return)...")
    subprocess.run(["osascript", "-e", 'tell application "Brave Browser" to activate'], check=True)
    time.sleep(0.3)
    run_agent_cmd(["press", "cmd+l"])
    time.sleep(0.5)
    
    run_agent_cmd(["clipboard-set", target_url])
    subprocess.run(["osascript", "-e", 'tell application "Brave Browser" to activate'], check=True)
    time.sleep(0.2)
    run_agent_cmd(["press", "cmd+v"])
    time.sleep(0.5)
    run_agent_cmd(["press", "return"])
    
    # STEP 3: Verification
    print("[4/4] Verifying page load...")
    success = False
    s2 = None
    for _ in range(12):
        time.sleep(1.5)
        s_curr = capture_full_dfs_tree(app_name="Brave Browser")
        if not s_curr.get("ok"):
            continue
        tree = s_curr.get("data", {}).get("tree", {})
        if find_node(tree, name_contains="YouTube") or "youtube" in str(s_curr).lower():
            s2 = s_curr
            success = True
            break
            
    if not s2:
        s2 = capture_full_dfs_tree(app_name="Brave Browser")
        
    logger.log_action("Navigate to URL", action_details={"url": target_url}, new_state=s2.get("data", {}).get("tree", {}))
    logger.finalize(success=success, notes=f"Brave opened '{target_url}' in private window. Success: {success}")
    print(f"\nTask Finished! Execution diff log saved to: {log_path}")

if __name__ == "__main__":
    main()
