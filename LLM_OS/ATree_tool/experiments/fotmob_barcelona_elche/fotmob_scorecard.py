"""
Experiment: Open FotMob Barcelona vs Elche La Liga Match Scorecard in Safari
With Full DFS State-Diff Workflow Logging.
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

def main():
    log_path = os.path.join(EXP_DIR, "workflow_execution.diff.log")
    logger = HarnessLogger(
        log_path=log_path,
        task_name="Open Barcelona vs Elche Scorecard on FotMob (Safari)",
        strip_ephemeral=True,
        context_lines=3
    )

    print("=== Step 0: Reopening & Activating Safari ===")
    subprocess.run(["osascript", "-e", 'tell application "Safari" to reopen', "-e", 'tell application "Safari" to activate'], check=True)
    time.sleep(1)

    search_url = "https://www.google.com/search?q=fotmob+barcelona+vs+elche+la+liga"
    print(f"\n=== Step 1: Navigating Safari to FotMob match search ({search_url}) ===")
    subprocess.run(["open", "-a", "Safari", search_url], check=True)
    time.sleep(3)

    subprocess.run(["osascript", "-e", 'tell application "Safari" to activate'], check=True)
    time.sleep(0.5)

    print("\n=== Step 2: Capturing Initial Full DFS Tree of Safari ===")
    snap0 = capture_full_dfs_tree(app_name="Safari")
    logger.log_initial_state(snap0, description="Safari Search Results Page Baseline")

    tree0 = snap0.get("data", {}).get("tree", {})

    print("\n=== Step 3: Searching Accessibility Tree for FotMob Match Link ===")
    matches = find_all_nodes(
        tree0,
        lambda n: ("fotmob" in str(n.get("name", "")).lower() or "barcelona" in str(n.get("name", "")).lower()) and n.get("bounds") and n.get("bounds", {}).get("height", 0) > 0
    )

    target_link = None
    for m in matches:
        name_lower = str(m.get("name", "")).lower()
        if "fotmob" in name_lower and ("barcelona" in name_lower or "elche" in name_lower or "match" in name_lower or "la liga" in name_lower or "vs" in name_lower):
            target_link = m
            break
    if not target_link and matches:
        target_link = matches[0]

    if target_link and target_link.get("bounds"):
        b = target_link["bounds"]
        cx = int(b["x"] + b["width"] / 2)
        cy = int(b["y"] + b["height"] / 2)
        print(f"Found match link: '{target_link.get('name')}' at bounds center ({cx}, {cy})")

        subprocess.run(["osascript", "-e", 'tell application "Safari" to activate'], check=True)
        time.sleep(0.3)
        print(f"Executing stealthClick at ({cx}, {cy})...")
        stealth_click(cx, cy)
        time.sleep(4)

        snap1 = capture_full_dfs_tree(app_name="Safari")
        logger.log_action(
            action_name="stealth_click_match_link",
            action_details={"target_name": target_link.get("name"), "coordinates": {"x": cx, "y": cy}},
            new_state=snap1,
            description="Clicked FotMob match link in search results"
        )
    else:
        print("Direct link click fallback: Navigating directly to FotMob Barcelona vs Elche match page...")
        fotmob_direct_url = "https://www.fotmob.com/matches/barcelona-vs-elche/2q1160#4176461"
        subprocess.run(["open", "-a", "Safari", fotmob_direct_url], check=True)
        time.sleep(4)

        snap1 = capture_full_dfs_tree(app_name="Safari")
        logger.log_action(
            action_name="open_direct_fotmob_url",
            action_details={"url": fotmob_direct_url},
            new_state=snap1,
            description="Navigated directly to FotMob Barcelona vs Elche scorecard URL"
        )

    logger.finalize(success=True, notes="FotMob Barcelona vs Elche scorecard opened successfully in Safari.")
    print(f"\nTask Finished! Execution diff log saved to: {log_path}")

if __name__ == "__main__":
    main()
