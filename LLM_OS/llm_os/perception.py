"""
LLM_OS Perception Engine.

Provides AX tree capture, state diffing, and tree summarization for the cognitive loop.
Wraps the existing ATree_tool utilities (dfs_tree.py, state_diff.py) and adds
an LLM-friendly tree summarization layer to keep context windows manageable.
"""
import json
import logging
import os
import sys
from typing import Optional

# Add ATree_tool to path for importing existing utilities
_ATREE_ROOT = os.path.join(os.path.dirname(__file__), '..', 'ATree_tool')
if _ATREE_ROOT not in sys.path:
    sys.path.insert(0, os.path.abspath(_ATREE_ROOT))

from utils.dfs_tree import capture_full_dfs_tree as _capture_full_dfs_tree
from utils.state_diff import generate_git_diff, normalize_tree_data

logger = logging.getLogger('llm_os.perception')


# ---------------------------------------------------------------------------
# State Capture
# ---------------------------------------------------------------------------

def capture_state(
    app_name: Optional[str] = None,
    window_id: Optional[str] = None,
    surface: Optional[str] = None,
    max_dfs_requests: int = 25,
) -> dict:
    """Capture a 100% complete, DFS-expanded AX tree snapshot.

    Recursively expands truncated container nodes (e.g. Electron webareas)
    to guarantee a fully serialized accessibility tree.

    Args:
        app_name: Target application name (e.g. "Calendar", "Notion").
        window_id: Specific window ID to scope the snapshot.
        surface: Surface type ("popover", "focused", etc.) for scoped capture.
        max_dfs_requests: Maximum recursive drill-down requests (default 25).

    Returns:
        Raw snapshot dict from agent-desktop with keys: ok, data.tree, data.snapshot_id.
    """
    logger.info(f'Capturing state: app={app_name}, window={window_id}, surface={surface}')

    snap = _capture_full_dfs_tree(
        app_name=app_name,
        window_id=window_id,
        surface=surface,
        max_requests=max_dfs_requests,
    )

    if snap.get('ok'):
        tree = snap.get('data', {}).get('tree', {})
        node_count = _count_nodes(tree)
        logger.info(f'State captured: {node_count} nodes')
    else:
        logger.warning(f'State capture failed: {snap}')

    return snap


def extract_tree(snapshot: dict) -> dict:
    """Extract the tree dict from a raw snapshot response."""
    return snapshot.get('data', {}).get('tree', {})


# ---------------------------------------------------------------------------
# State Diffing
# ---------------------------------------------------------------------------

def compute_diff(
    prev_tree: dict,
    curr_tree: dict,
    context_lines: int = 3,
    strip_ephemeral: bool = True,
) -> str:
    """Generate a git-style unified diff between two AX tree states.

    Strips volatile session identifiers (snapshot hashes, ref_id prefixes)
    so diffs focus on meaningful UI mutations.

    Args:
        prev_tree: The previous step's AX tree.
        curr_tree: The current step's AX tree.
        context_lines: Number of context lines around changes.
        strip_ephemeral: Whether to strip session-specific IDs.

    Returns:
        Unified diff string with +/- lines, or "(No state change detected)".
    """
    return generate_git_diff(
        prev_tree,
        curr_tree,
        context_lines=context_lines,
        strip_ephemeral=strip_ephemeral,
    )


# ---------------------------------------------------------------------------
# Tree Search
# ---------------------------------------------------------------------------

def find_node(tree: dict, predicate) -> Optional[dict]:
    """DFS search for a node matching a predicate function.

    Args:
        tree: The AX tree root node.
        predicate: A callable(node) -> bool.

    Returns:
        First matching node dict, or None.
    """
    if not isinstance(tree, dict):
        return None
    if predicate(tree):
        return tree
    for child in tree.get('children', []):
        found = find_node(child, predicate)
        if found:
            return found
    return None


def find_node_by_ref_id(tree: dict, ref_id: str) -> Optional[dict]:
    """Find a node by its ref_id value."""
    return find_node(tree, lambda n: n.get('ref_id') == ref_id)


def find_node_by_name(tree: dict, name: str, role: Optional[str] = None) -> Optional[dict]:
    """Find a node by name (case-insensitive), optionally filtered by role."""
    def predicate(n):
        node_name = str(n.get('name', '')).lower()
        if name.lower() not in node_name:
            return False
        if role and n.get('role') != role:
            return False
        return True
    return find_node(tree, predicate)


def find_all_nodes(tree: dict, predicate) -> list[dict]:
    """DFS search returning ALL nodes matching a predicate."""
    results = []
    _find_all_recursive(tree, predicate, results)
    return results


def _find_all_recursive(node: dict, predicate, results: list):
    if not isinstance(node, dict):
        return
    if predicate(node):
        results.append(node)
    for child in node.get('children', []):
        _find_all_recursive(child, predicate, results)


def get_node_center(node: dict) -> Optional[tuple[int, int]]:
    """Calculate the center pixel coordinates of a node from its bounds.

    Returns:
        (x, y) center coordinates, or None if bounds are missing.
    """
    bounds = node.get('bounds')
    if not bounds:
        return None
    x = int(bounds['x'] + bounds['width'] / 2)
    y = int(bounds['y'] + bounds['height'] / 2)
    return (x, y)


# ---------------------------------------------------------------------------
# LLM-Friendly Tree Summarization
# ---------------------------------------------------------------------------

def summarize_tree_for_llm(
    tree: dict,
    max_depth: int = 5,
    max_children_per_node: int = 30,
    include_bounds: bool = True,
) -> str:
    """Produce a compact, indented text representation of the AX tree for LLM context.

    Preserves actionable information (role, name, ref_id, bounds, states)
    while truncating deeply nested children to keep token usage manageable.

    A raw JSON tree can be 2MB+. This typically produces 10-50KB of text.

    Args:
        tree: The AX tree root dict.
        max_depth: Maximum depth to render (deeper nodes summarized as "... N children").
        max_children_per_node: Max children to render per node before truncating.
        include_bounds: Whether to include bounding box coordinates.

    Returns:
        Indented text representation of the tree.
    """
    lines: list[str] = []
    _summarize_node(tree, lines, depth=0, max_depth=max_depth,
                    max_children=max_children_per_node, include_bounds=include_bounds)
    return '\n'.join(lines)


def _summarize_node(
    node: dict,
    lines: list[str],
    depth: int,
    max_depth: int,
    max_children: int,
    include_bounds: bool,
):
    """Recursively render a tree node into compact text lines."""
    if not isinstance(node, dict):
        return

    indent = '  ' * depth

    # Build the node description line
    role = node.get('role', '?')
    name = node.get('name', '')
    ref_id = node.get('ref_id', '')
    states = node.get('states', [])

    parts = [f'[{role}]']

    if name:
        # Truncate very long names (e.g. full document text)
        display_name = name[:120] + '...' if len(str(name)) > 120 else name
        parts.append(f'"{display_name}"')

    if ref_id:
        parts.append(f'ref={ref_id}')

    if states:
        parts.append(f'states={states}')

    if include_bounds and node.get('bounds'):
        b = node['bounds']
        parts.append(f'@({b.get("x", 0)},{b.get("y", 0)},{b.get("width", 0)}x{b.get("height", 0)})')

    lines.append(f'{indent}{" ".join(parts)}')

    # Handle children
    children = node.get('children', [])
    children_count = node.get('children_count', len(children))

    if depth >= max_depth:
        if children_count > 0:
            lines.append(f'{indent}  ... ({children_count} children, depth limit reached)')
        return

    if len(children) > max_children:
        # Render first and last few, with truncation notice
        half = max_children // 2
        for child in children[:half]:
            _summarize_node(child, lines, depth + 1, max_depth, max_children, include_bounds)
        lines.append(f'{indent}  ... ({len(children) - max_children} more children omitted)')
        for child in children[-half:]:
            _summarize_node(child, lines, depth + 1, max_depth, max_children, include_bounds)
    else:
        for child in children:
            _summarize_node(child, lines, depth + 1, max_depth, max_children, include_bounds)


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _count_nodes(tree: dict) -> int:
    """Count total nodes in a tree."""
    if not isinstance(tree, dict):
        return 0
    count = 1
    for child in tree.get('children', []):
        count += _count_nodes(child)
    return count
