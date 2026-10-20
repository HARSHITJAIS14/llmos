"""The OLD ATree_tool state_diff implementation, vendored verbatim as the
benchmark baseline. tests/test_axdiff.py asserts core.axdiff beats this by
>=5x on the bloated fixture pairs. Do not 'fix' this file — its flaws are
the point."""
import json
import difflib
import re


def normalize_tree_data(tree_data, strip_ephemeral=False):
    if isinstance(tree_data, str):
        try:
            tree_data = json.loads(tree_data)
        except Exception:
            lines = tree_data.splitlines(keepends=True)
            return [l if l.endswith('\n') else l + '\n' for l in lines]

    def flatten(node, path=""):
        flat = {}
        if not isinstance(node, dict):
            return flat

        attrs = {k: v for k, v in node.items() if k not in ["children"]}

        if strip_ephemeral:
            if "snapshot_id" in attrs:
                del attrs["snapshot_id"]
            if "ref_id" in attrs and isinstance(attrs["ref_id"], str):
                attrs["ref_id"] = re.sub(r"^@[a-zA-Z0-9]+:", ":", attrs["ref_id"])

        flat[path] = attrs

        counts = {}
        for child in node.get("children", []):
            if not isinstance(child, dict):
                continue
            c_role = child.get("role", "")
            c_name = child.get("name", child.get("label", ""))
            c_key = f"{c_role}:{c_name}"
            counts[c_key] = counts.get(c_key, 0) + 1
            c_path = f"{path}/{c_key}[{counts[c_key]}]"
            flat.update(flatten(child, c_path))

        return flat

    flat_tree = flatten(tree_data)

    lines = []
    for k in sorted(flat_tree.keys()):
        lines.append(f"{k} => {json.dumps(flat_tree[k], sort_keys=True)}\n")

    return lines


def generate_git_diff(prev_state, curr_state, context_lines=3,
                      from_label="State T-1", to_label="State T",
                      strip_ephemeral=False):
    prev_lines = normalize_tree_data(prev_state, strip_ephemeral=strip_ephemeral)
    curr_lines = normalize_tree_data(curr_state, strip_ephemeral=strip_ephemeral)

    diff = list(difflib.unified_diff(
        prev_lines, curr_lines,
        fromfile=from_label, tofile=to_label, n=context_lines,
    ))

    if not diff:
        return "(No state change detected)\n"

    return "".join(diff)
