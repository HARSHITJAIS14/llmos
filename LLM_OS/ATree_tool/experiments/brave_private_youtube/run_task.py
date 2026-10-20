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
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com"
    exp_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(exp_dir, "workflow_execution.diff.log")
    
    logger = HarnessLogger(
        log_path=log_path,
        task_name="Open YouTube in Brave Private Window",
        strip_ephemeral=True,
        context_lines=3
    )
    
    # STEP 0: Activate Brave Browser
    print("=== Step 0: Activating Brave Browser ===")
    subprocess.run(["osascript", "-e", 'tell application "Brave Browser" to reopen', "-e", 'tell application "Brave Browser" to activate'], check=True)
    time.sleep(1.5)
    
    # Baseline Capture S0
    print("Capturing baseline S0...")
    s0 = capture_full_dfs_tree(app_name="Brave Browser")
    if not s0.get("ok"):
        s0 = capture_full_dfs_tree()
    logger.log_initial_state(s0.get("data", {}).get("tree", {}), description="Brave Browser Baseline State")
    
    # STEP 1: Open New Private Window (Cmd+Shift+N)
    print("=== Step 1: Opening Private Window (Cmd+Shift+N) ===")
    subprocess.run(["osascript", "-e", 'tell application "Brave Browser" to activate'], check=True)
    time.sleep(0.3)
    run_agent_cmd(["press", "cmd+shift+n"])
    time.sleep(1.5)
    
    s1 = capture_full_dfs_tree(app_name="Brave Browser")
    logger.log_action("Open Private Window", action_details={"keys": "cmd+shift+n"}, new_state=s1.get("data", {}).get("tree", {}), description="Opened new private window in Brave Browser")
    
    # STEP 2: Focus Address Bar & Navigate to YouTube
    print(f"=== Step 2: Navigating to '{target_url}' ===")
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
    
    # STEP 3: Cognitive Loop to Verify Page Load
    print("=== Step 3: Verifying YouTube Page Load ===")
    s2 = None
    success = False
    for attempt in range(12):
        time.sleep(1.5)
        print(f"Polling page load... attempt {attempt + 1}")
        s_curr = capture_full_dfs_tree(app_name="Brave Browser")
        if not s_curr.get("ok"):
            continue
        tree = s_curr.get("data", {}).get("tree", {})
        
        # Check if YouTube or video elements appear in tree
        yt_node = find_node(tree, name_contains="YouTube") or find_node(tree, role="webarea")
        if yt_node and "youtube" in str(s_curr).lower():
            s2 = s_curr
            success = True
            break
            
    if not s2:
        s2 = capture_full_dfs_tree(app_name="Brave Browser")
        
    logger.log_action("Navigate to YouTube", action_details={"url": target_url, "keys": "cmd+l -> cmd+v -> return"}, new_state=s2.get("data", {}).get("tree", {}), description="Navigated to YouTube and verified page load in private window")
    
    logger.finalize(success=success, notes=f"YouTube opened on private window in Brave Browser. Verification: {success}")
    print(f"\nExecution Finished! Success: {success}. Diff log: {log_path}")

if __name__ == "__main__":
    main()
