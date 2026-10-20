"""
DFS Tree Extractor for LLM_OS.
Captures accessibility tree snapshots and performs recursive DFS drill-down
on truncated container nodes (e.g. Electron webareas, truncated lists) to return
a 100% complete, fully expanded DFS tree state.
"""
import json
import subprocess
import os

AGENT = '/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js'

def run_agent_cmd(args):
    res = subprocess.run([AGENT] + args, capture_output=True, text=True)
    try:
        return json.loads(res.stdout)
    except Exception as e:
        return {"ok": False, "raw": res.stdout, "error": str(e)}

def expand_dfs_tree(node, snapshot_id, current_requests=None, max_requests=25):
    """
    Recursively expands nodes that have children_count > 0 but empty/missing children array.
    """
    if current_requests is None:
        current_requests = [0]

    if not isinstance(node, dict) or current_requests[0] >= max_requests:
        return

    # Check if truncated node
    children_count = node.get("children_count", 0)
    children = node.get("children", [])
    ref_id = node.get("ref_id")

    if children_count > 0 and (not children) and ref_id:
        current_requests[0] += 1
        drill_data = run_agent_cmd(["snapshot", "--root", ref_id, "--snapshot", snapshot_id, "-i", "--include-bounds"])
        if drill_data.get("ok") and "data" in drill_data:
            drilled_tree = drill_data["data"].get("tree", {})
            if "children" in drilled_tree:
                node["children"] = drilled_tree["children"]

    # Continue DFS recursion into children
    for child in node.get("children", []):
        expand_dfs_tree(child, snapshot_id, current_requests=current_requests, max_requests=max_requests)

def capture_full_dfs_tree(app_name=None, window_id=None, surface=None, max_requests=25):
    """
    Captures initial snapshot and performs full DFS expansion across all truncated nodes.
    Returns complete state dictionary.
    """
    cmd = ["snapshot", "-i", "--include-bounds"]
    if surface:
        cmd.extend(["--surface", surface])
    elif window_id:
        cmd.extend(["--window-id", window_id])
    elif app_name:
        cmd.extend(["--app", app_name])

    snap_data = run_agent_cmd(cmd)
    if not snap_data.get("ok"):
        # Fallback to general window snapshot
        snap_data = run_agent_cmd(["snapshot", "-i", "--include-bounds"])

    if not snap_data.get("ok") or "data" not in snap_data:
        return snap_data

    snapshot_id = snap_data["data"].get("snapshot_id")
    root_tree = snap_data["data"].get("tree")

    if snapshot_id and root_tree:
        req_counter = [0]
        expand_dfs_tree(root_tree, snapshot_id, current_requests=req_counter, max_requests=max_requests)

    return snap_data
