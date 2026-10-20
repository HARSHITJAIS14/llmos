"""
Experiment: Capture Notion Window Screenshot and Send to Contact on WhatsApp.
With Full DFS State-Diff Workflow Logging.

Usage:
  python3 experiments/notion_screenshot_whatsapp/run_task.py "niga"
"""
import os
import sys
import json
import time
import subprocess

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

def find_all_nodes(n, predicate, results=None):
    if results is None:
        results = []
    if not isinstance(n, dict):
        return results
    if predicate(n):
        results.append(n)
    for c in n.get("children", []):
        find_all_nodes(c, predicate, results)
    return results


def find_whatsapp_window():
    all_wins = run_agent_cmd(["list-windows"])
    if not all_wins.get("ok"):
        return None
    for w in all_wins.get("data", []):
        if w.get("visible") and "WhatsApp" in str(w.get("title", "")):
            return w
    return None

def main():
    contact_name = sys.argv[1] if len(sys.argv) > 1 else "niga"
    screenshot_path = os.path.join(EXP_DIR, "notion_screenshot.png")
    log_path = os.path.join(EXP_DIR, "workflow_execution.diff.log")

    logger = HarnessLogger(
        log_path=log_path,
        task_name=f"Send Notion Screenshot to WhatsApp Contact '{contact_name}'",
        strip_ephemeral=True,
        context_lines=3
    )

    # STEP 0: Activate Notion & Capture Baseline Full DFS Tree
    print("=== Step 0: Activating Notion ===")
    subprocess.run(["osascript", "-e", 'tell application "Notion" to reopen', "-e", 'tell application "Notion" to activate'], check=True)
    time.sleep(1.5)

    print("[Harness] Capturing Notion Full DFS Baseline State...")
    snap0 = capture_full_dfs_tree(app_name="Notion")
    logger.log_initial_state(snap0, description="Initial Notion Window Baseline")

    # STEP 1: Take Screenshot of Notion Window
    print(f"\n=== Step 1: Taking Screenshot of Notion Window -> {screenshot_path} ===")
    subprocess.run(["osascript", "-e", 'tell application "Notion" to activate'], check=True)
    time.sleep(0.5)

    # Find window ID if available
    win_out = run_agent_cmd(["list-windows", "--app", "Notion"])
    target_win = None
    if win_out.get("ok"):
        for w in win_out.get("data", []):
            if w.get("visible") and w.get("title"):
                target_win = w
                break
        if not target_win and win_out.get("data"):
            target_win = win_out["data"][0]

    if target_win and target_win.get("id"):
        win_id_str = str(target_win["id"]).replace("w-", "")
        print(f"Capturing Notion window ID: {target_win['id']}")
        subprocess.run(["screencapture", "-l", win_id_str, screenshot_path], check=False)

    if not os.path.exists(screenshot_path) or os.path.getsize(screenshot_path) == 0:
        print("Fallback window capture...")
        subprocess.run(["screencapture", "-x", screenshot_path], check=True)

    print(f"✓ Screenshot captured: {screenshot_path} (Size: {os.path.getsize(screenshot_path)} bytes)")

    # STEP 2: Launch & Activate WhatsApp
    print("\n=== Step 2: Launching & Activating WhatsApp ===")
    subprocess.run(["open", "-a", "WhatsApp"], check=True)
    time.sleep(2.5)
    subprocess.run(["osascript", "-e", 'tell application "WhatsApp" to activate'], check=True)
    time.sleep(1)

    wa_win = find_whatsapp_window()
    if not wa_win:
        print("Error: WhatsApp window not found.")
        sys.exit(1)

    print(f"Found WhatsApp window: {wa_win.get('id')} '{wa_win.get('title')}'")

    # STEP 3: Search for Contact on WhatsApp
    print(f"\n=== Step 3: Searching for contact '{contact_name}' ===")
    wa_snap = run_agent_cmd(["snapshot", "--window-id", wa_win["id"], "-i", "--include-bounds"])
    wa_tree = wa_snap.get("data", {}).get("tree", {})

    search_field = find_node(
        wa_tree,
        lambda n: n.get("role") == "textfield" and "search" in str(n.get("name", "")).lower() and n.get("bounds")
    )

    if search_field and search_field.get("bounds"):
        b = search_field["bounds"]
        cx, cy = int(b["x"] + b["width"] / 2), int(b["y"] + b["height"] / 2)
        print(f"Clicking search field at ({cx}, {cy})...")
        subprocess.run(["osascript", "-e", 'tell application "WhatsApp" to activate'], check=True)
        time.sleep(0.2)
        stealth_click(cx, cy)
        time.sleep(0.5)

    run_agent_cmd(["clipboard-set", contact_name])
    subprocess.run(["osascript", "-e", 'tell application "WhatsApp" to activate'], check=True)
    time.sleep(0.2)
    run_agent_cmd(["press", "cmd+v"])
    time.sleep(2)

    # Find matching contact cell/button
    post_search_snap = run_agent_cmd(["snapshot", "--window-id", wa_win["id"], "-i", "--include-bounds"])
    post_search_tree = post_search_snap.get("data", {}).get("tree", {})

    contact_node = find_node(
        post_search_tree,
        lambda n: (n.get("role") in ["button", "cell", "statictext"]) and
                  contact_name.lower().split()[0] in str(n.get("name", "")).lower() and
                  n.get("bounds") and n.get("bounds", {}).get("height", 0) > 0
    )

    if contact_node and contact_node.get("bounds"):
        b = contact_node["bounds"]
        cx, cy = int(b["x"] + b["width"] / 2), int(b["y"] + b["height"] / 2)
        print(f"Clicking contact '{contact_node.get('name')}' at ({cx}, {cy})...")
        subprocess.run(["osascript", "-e", 'tell application "WhatsApp" to activate'], check=True)
        time.sleep(0.2)
        stealth_click(cx, cy)
        time.sleep(1)
    else:
        print("Contact node not directly in tree, pressing Return...")
        run_agent_cmd(["press", "return"])
        time.sleep(1)

    # STEP 4: Copy Screenshot Image to macOS Clipboard via AppleScript
    print("\n=== Step 4: Copying Screenshot Image to Clipboard ===")
    copy_applescript = f'set the clipboard to (read (POSIX file "{os.path.abspath(screenshot_path)}") as «class PNGf»)'
    subprocess.run(["osascript", "-e", copy_applescript], check=True)
    time.sleep(0.5)

    # STEP 4.5: MANDATORY RECIPIENT CHAT HEADER VERIFICATION
    print("\n=== Step 4.5: VERIFYING RECIPIENT CHAT HEADER ===")
    chat_verify_snap = run_agent_cmd(["snapshot", "--window-id", wa_win["id"], "-i", "--include-bounds"])
    chat_verify_tree = chat_verify_snap.get("data", {}).get("tree", {})

    target_first_name = contact_name.lower().split()[0]
    header_nodes = find_all_nodes(
        chat_verify_tree,
        lambda n: target_first_name in str(n.get("name", "")).lower() and n.get("role") in ["button", "statictext", "cell", "header"]
    )

    if not header_nodes:
        print(f"❌ SAFETY ERROR: Active chat header does NOT match target contact '{contact_name}'. Aborting send to prevent wrong dispatch!")
        logger.finalize(success=False, notes=f"RECIPIENT_MISMATCH_ERROR: Active chat header did not match '{contact_name}'. Aborted dispatch.")
        sys.exit(1)

    matched_name = header_nodes[0].get("name", "")
    print(f"✓ RECIPIENT VERIFIED: Active chat header matches target contact ('{matched_name}'). Safe to proceed.")

    # STEP 5: Focus WhatsApp Compose Field and Paste Image
    print("\n=== Step 5: Pasting & Sending Image on WhatsApp ===")

    chat_snap = run_agent_cmd(["snapshot", "--window-id", wa_win["id"], "-i", "--include-bounds"])
    chat_tree = chat_snap.get("data", {}).get("tree", {})

    compose_field = find_node(
        chat_tree,
        lambda n: n.get("role") == "textfield" and "compose" in str(n.get("name", "")).lower() and n.get("bounds")
    )

    if compose_field and compose_field.get("bounds"):
        b = compose_field["bounds"]
        cx, cy = int(b["x"] + b["width"] / 2), int(b["y"] + b["height"] / 2)
        subprocess.run(["osascript", "-e", 'tell application "WhatsApp" to activate'], check=True)
        time.sleep(0.2)
        stealth_click(cx, cy)
        time.sleep(0.3)
    else:
        # Fallback click near bottom of WhatsApp window
        win_bounds = chat_tree.get("bounds") or {"x": 500, "y": 500, "width": 800, "height": 600}
        cx = int(win_bounds["x"] + win_bounds["width"] / 2)
        cy = int(win_bounds["y"] + win_bounds["height"] - 50)
        subprocess.run(["osascript", "-e", 'tell application "WhatsApp" to activate'], check=True)
        time.sleep(0.2)
        stealth_click(cx, cy)
        time.sleep(0.3)

    print("Pasting image (Cmd+V)...")
    run_agent_cmd(["press", "cmd+v"])
    time.sleep(1.5)

    print("Sending image (Return)...")
    run_agent_cmd(["press", "return"])
    time.sleep(2)

    # STEP 6: Capture Final Full DFS Tree and Log State Diff
    snap_final = capture_full_dfs_tree(app_name="WhatsApp")
    logger.log_action(
        action_name="send_notion_screenshot_whatsapp",
        action_details={"contact": contact_name, "screenshot": screenshot_path},
        new_state=snap_final,
        description=f"Pasted and dispatched Notion screenshot to '{contact_name}' on WhatsApp"
    )

    logger.finalize(success=True, notes=f"Notion screenshot sent to '{contact_name}' successfully.")
    print(f"\nTask Finished! Execution diff log saved to: {log_path}")

if __name__ == "__main__":
    main()
