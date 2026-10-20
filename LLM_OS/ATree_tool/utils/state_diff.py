"""
Utility module for tree state normalization and git-style unified diff generation.
Used by the LLM_OS Harness to track state transitions (tree_state, action) across task steps.
"""
import json
import difflib
import re

def normalize_tree_data(tree_data, strip_ephemeral=False):
    """
    Converts a tree dictionary or snapshot JSON into a canonical multi-line JSON string representation.
    
    If strip_ephemeral is True, strips volatile session identifiers like snapshot_id
    and snapshot hashes from ref_ids (e.g. @s1faoqstpdf3hc:e1 -> :e1) so diffs focus on
    semantic UI modifications.
    """
    if isinstance(tree_data, str):
        try:
            tree_data = json.loads(tree_data)
        except Exception:
            lines = tree_data.splitlines(keepends=True)
            return [l if l.endswith('\n') else l + '\n' for l in lines]

    # Deep copy
    data_copy = json.loads(json.dumps(tree_data))

    if strip_ephemeral:
        def clean_node(node):
            if isinstance(node, dict):
                if "snapshot_id" in node:
                    del node["snapshot_id"]
                if "ref_id" in node and isinstance(node["ref_id"], str):
                    node["ref_id"] = re.sub(r"^@[a-zA-Z0-9]+:", ":", node["ref_id"])
                for v in node.values():
                    clean_node(v)
            elif isinstance(node, list):
                for item in node:
                    clean_node(item)

        clean_node(data_copy)

    formatted_str = json.dumps(data_copy, indent=2, sort_keys=True)
    lines = formatted_str.splitlines(keepends=True)
    return [l if l.endswith('\n') else l + '\n' for l in lines]


def generate_git_diff(prev_state, curr_state, context_lines=3, from_label="State T-1", to_label="State T", strip_ephemeral=False):
    """
    Generates a git-style unified diff string (+ added, - deleted, @@ header context)
    comparing prev_state and curr_state.
    """
    prev_lines = normalize_tree_data(prev_state, strip_ephemeral=strip_ephemeral)
    curr_lines = normalize_tree_data(curr_state, strip_ephemeral=strip_ephemeral)

    diff = list(difflib.unified_diff(
        prev_lines,
        curr_lines,
        fromfile=from_label,
        tofile=to_label,
        n=context_lines
    ))
    
    if not diff:
        return "(No state change detected)\n"

    return "".join(diff)
