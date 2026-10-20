#!/usr/bin/env python3
"""
Experiment: Open LLM OS Page in Notion

Description:
1. Reopens and activates Notion using osascript.
2. Captures full DFS accessibility tree state (utils.dfs_tree.capture_full_dfs_tree) for baseline S0.
3. Checks if the target page is already active. If not, dispatches Cmd+P to open Notion Quick Find.
4. Pastes the target page title ("LLM OS") into the search box and hits Return.
5. Polls and verifies that the main webarea/page title updates to "LLM OS".
6. Logs all state transition diffs (+/- git style) to workflow_execution.diff.log.

Usage:
  python3 experiments/notion_open_llm_os/open_notion_llm_os.py
  python3 experiments/notion_open_llm_os/open_notion_llm_os.py "LLM OS"
"""
import os
import sys
import time
import subprocess
import json
import datetime

# Add root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from utils.harness_logger import HarnessLogger
from utils.dfs_tree import capture_full_dfs_tree, run_agent_cmd

def find_node(tree, **kwargs):
    """Recursively search for a node matching the kwargs."""
    if not isinstance(tree, dict):
        return None
        
    match = True
    for k, v in kwargs.items():
        if k == "name_contains":
            if v.lower() not in str(tree.get("name", "")).lower():
                match = False
                break
        elif k == "value_contains":
            if v.lower() not in str(tree.get("value", "")).lower():
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

def is_page_active(tree, page_name):
    """Check if the given page is active in Notion webarea."""
    if not isinstance(tree, dict):
        return False
    # Check webareas
    if tree.get("role") == "webarea" and page_name.lower() in str(tree.get("name", "")).lower():
        return True
    for child in tree.get("children", []):
        if is_page_active(child, page_name):
            return True
    return False

def main():
    target_page = sys.argv[1] if len(sys.argv) > 1 else "LLM OS"
    exp_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(exp_dir, "workflow_execution.diff.log")
    
    logger = HarnessLogger(
        log_path=log_path,
        task_name=f"Open Notion Page ('{target_page}')",
        strip_ephemeral=True,
        context_lines=3
    )
    
    # STEP 0: Reopen and Activate Notion
    print("[1/4] Activating Notion...")
    subprocess.run(["osascript", "-e", 'tell application "Notion" to reopen', "-e", 'tell application "Notion" to activate'], check=True)
    time.sleep(1.5)
    
    # Baseline Capture S0
    print("[2/4] Capturing Baseline Accessibility Tree (S0)...")
    s0 = capture_full_dfs_tree(app_name="Notion", max_requests=30)
    with open(os.path.join(exp_dir, "state_s0.json"), "w") as f:
        json.dump(s0, f, indent=2)
    logger.log_initial_state(s0.get("data", {}).get("tree", {}), description="Notion Baseline State S0")
    
    tree_s0 = s0.get("data", {}).get("tree", {})
    if is_page_active(tree_s0, target_page):
        print(f"Page '{target_page}' is already active in Notion.")
        logger.finalize(success=True, notes=f"Page '{target_page}' was already active.")
        return

    # STEP 1: Trigger Quick Find (Cmd+P)
    print(f"[3/4] Triggering Quick Find for '{target_page}' (Cmd+P)...")
    subprocess.run(["osascript", "-e", 'tell application "Notion" to activate'], check=True)
    time.sleep(0.3)
    run_agent_cmd(["press", "cmd+p"])
    time.sleep(1.0)
    
    s1 = capture_full_dfs_tree(app_name="Notion", max_requests=30)
    logger.log_action(
        "Trigger Quick Find (Cmd+P)",
        action_details={"keys": "cmd+p"},
        new_state=s1.get("data", {}).get("tree", {}),
        description="Trigger Quick Find modal dialog."
    )
    
    # STEP 2: Paste Target Page & Hit Return
    print(f"[4/4] Pasting '{target_page}' into Quick Find and confirming...")
    run_agent_cmd(["clipboard-set", target_page])
    time.sleep(0.2)
    subprocess.run(["osascript", "-e", 'tell application "Notion" to activate'], check=True)
    time.sleep(0.2)
    run_agent_cmd(["press", "cmd+v"])
    time.sleep(0.5)
    run_agent_cmd(["press", "return"])
    
    # Verification
    print("Verifying page load...")
    success = False
    s2 = None
    for attempt in range(8):
        time.sleep(1.5)
        s_curr = capture_full_dfs_tree(app_name="Notion", max_requests=30)
        if not s_curr.get("ok"):
            continue
        tree = s_curr.get("data", {}).get("tree", {})
        if is_page_active(tree, target_page):
            s2 = s_curr
            success = True
            break
            
    if not s2:
        s2 = capture_full_dfs_tree(app_name="Notion", max_requests=30)
        
    with open(os.path.join(exp_dir, "state_final.json"), "w") as f:
        json.dump(s2, f, indent=2)
        
    logger.log_action(
        f"Navigate to '{target_page}'",
        action_details={"target_page": target_page, "method": "Cmd+P -> Cmd+V -> Return"},
        new_state=s2.get("data", {}).get("tree", {}),
        description=f"Pasted '{target_page}' and pressed Return to load page."
    )
    logger.finalize(success=success, notes=f"Notion opened '{target_page}'. Success: {success}")
    print(f"\nTask Finished! Execution diff log saved to: {log_path}")

if __name__ == "__main__":
    main()
