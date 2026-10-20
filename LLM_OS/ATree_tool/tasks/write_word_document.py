#!/usr/bin/env python3
"""
Write Word Document Task
Activates MS Word, creates a new document, pastes perfectly formatted RTF (from HTML),
and executes a cognitive loop to natively navigate the Save dialog.
"""
import os
import sys
import time
import subprocess
import datetime

# Add the root directory to sys.path to import utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.harness_logger import HarnessLogger
from utils.dfs_tree import capture_full_dfs_tree, run_agent_cmd

def setup_essay_clipboard(html_content, temp_dir):
    essay_html_path = os.path.join(temp_dir, "temp_essay.html")
    essay_rtf_path = os.path.join(temp_dir, "temp_essay.rtf")
    
    with open(essay_html_path, "w") as f:
        f.write(html_content)
    
    # Convert HTML to RTF using macOS textutil (preserves formatting perfectly)
    subprocess.run(["textutil", "-convert", "rtf", essay_html_path], check=True)
    
    # Load into macOS clipboard as true public.rtf using AppleScript
    applescript_cmd = f'set the clipboard to (read (POSIX file "{essay_rtf_path}") as "RTF ")'
    subprocess.run(["osascript", "-e", applescript_cmd], check=True)

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
    if len(sys.argv) < 3:
        print("Usage: python write_word_document.py <filename> <html_content>")
        sys.exit(1)
        
    filename = sys.argv[1]
    html_content = sys.argv[2]
    
    # Setup Logging in tasks/logs/
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(logs_dir, f"write_word_{timestamp}.diff.log")
    
    logger = HarnessLogger(log_path, task_name=f"Write Word Document ({filename})")
    
    # 1. Setup clipboard
    temp_dir = os.path.join(os.path.dirname(__file__), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    setup_essay_clipboard(html_content, temp_dir)
    print("[1/5] Prepared formatted RTF in the clipboard.")
    
    # 2. Activate Word safely and open New Document
    print("[2/5] Activating Microsoft Word...")
    subprocess.run(["osascript", "-e", 'tell application "Microsoft Word" to reopen', "-e", 'tell application "Microsoft Word" to activate'])
    time.sleep(1)
    run_agent_cmd(["press", "cmd+n"])
    time.sleep(2)
    
    # 3. Capture baseline state
    s0 = capture_full_dfs_tree("Microsoft Word")
    if not s0.get("ok"):
        logger.finalize(success=False, notes="Failed to capture S0")
        return
    logger.log_initial_state(s0["data"]["tree"], description="Blank Document")
    
    # 4. Paste RTF
    print("[3/5] Pasting text with formatting...")
    run_agent_cmd(["press", "cmd+v"])
    time.sleep(2)
    
    s1 = capture_full_dfs_tree("Microsoft Word")
    logger.log_action("Paste Formatted Text", action_details={"keys": "cmd+v"}, new_state=s1["data"]["tree"])
    
    # 5. Save Dialog Trigger
    print("[4/5] Triggering Save Dialog...")
    run_agent_cmd(["press", "cmd+s"])
    
    # 6. Cognitive Loop to wait for save dialog sheet
    s2 = None
    save_textfield = None
    save_button = None
    for attempt in range(10):
        time.sleep(1)
        s_current = capture_full_dfs_tree("Microsoft Word")
        if not s_current.get("ok"):
            continue
            
        tree = s_current["data"]["tree"]
        save_textfield = find_node(tree, native_id="saveAsNameTextField")
        save_button = find_node(tree, native_id="OKButton")
        
        if save_textfield and save_button:
            s2 = s_current
            break
            
    if not s2:
        print("Save dialog did not appear or nodes not found.")
        logger.finalize(success=False, notes="Save dialog failed.")
        return
        
    logger.log_action("Trigger Save Dialog", action_details={"keys": "cmd+s"}, new_state=s2["data"]["tree"])
    
    # 7. Name the document and click Save
    print(f"[5/5] Setting filename to '{filename}' and saving...")
    tf_ref = save_textfield.get("ref_id")
    btn_ref = save_button.get("ref_id")
    snap_id = s2["data"]["snapshot_id"]
    
    run_agent_cmd(["set-value", tf_ref, filename, "--snapshot", snap_id])
    run_agent_cmd(["click", btn_ref, "--snapshot", snap_id])
    
    # 8. Verify save completion
    time.sleep(2)
    s3 = capture_full_dfs_tree("Microsoft Word")
    logger.log_action("Set Name and Save", action_details={"filename": filename}, new_state=s3["data"]["tree"])
    
    logger.finalize(success=True, notes="Successfully pasted formatted essay and saved.")
    print(f"Done! Check the log: {log_path}")

if __name__ == "__main__":
    main()
