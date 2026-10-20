"""label(), region(), and the child-label pass (implementation.md §6.10).

label() is the one string that names a node to people and models. It follows the TXT/ID
laws: statictext name-or-value (never both), textfield identity-in-value, rows/cells from
children, heading value is its level, WhatsApp packs a record into button.value.
"""
from __future__ import annotations

from ..types import Node, Rect, Snapshot
from .normalize import checked_value, norm

LABEL_FROM_CHILDREN = frozenset({"button", "link", "cell", "row", "treeitem", "radiobutton",
                                 "checkbox", "menuitem", "tab", "listitem", "option"})
_LRM = "‎"


def _text(v) -> str:
    return norm(v) if isinstance(v, str) else ""


def label(node: Node, snap: Snapshot | None = None, limit: int = 120) -> str:
    role = node.role
    if role == "statictext":
        out = node.name or _text(node.value)                            # LAW-TXT-2
    elif role == "textfield":
        out = node.name or _text(node.value)                            # LAW-ID-4
    elif role in ("cell", "row"):
        out = node.description or node.name                             # LAW-TXT-4, ID-5
        if not out and snap is not None:
            out = _join_children(node, snap, 80)
    elif role == "heading":
        out = node.name                                                 # LAW-TXT-6
    elif role == "button" and isinstance(node.value, str) and node.value.startswith(_LRM) and "," in node.value:
        out = norm(node.value.split(",")[0])                            # LAW-TXT-5 (WhatsApp rows)
    else:
        out = node.name or (node.description if node.description != node.name else "")
    if role in ("checkbox", "switch", "radiobutton"):
        state = checked_value(node.value)
        if state is not None and out != _text(node.value):
            out = f"{out} [{'on' if state else 'off'}]".strip()
    return out[:limit]


def _join_children(node: Node, snap: Snapshot, limit: int) -> str:
    parts: list[str] = []
    total = 0
    for child in snap.subtree(node.alias)[1:]:
        t = child.name or (_text(child.value) if child.role in ("statictext", "textfield") else "")
        if t and t not in parts:
            parts.append(t)
            total += len(t) + 1
            if total >= limit:
                break
    return " ".join(parts)[:limit]


def fill_child_labels(snap: Snapshot) -> None:
    """Names from children (agent-desktop's child label) and placeholders, after the walk. No IPC."""
    for node in snap.iter():
        if node.name:
            continue
        if node.role in LABEL_FROM_CHILDREN:
            for cid in node.children:
                child = snap.nodes.get(cid)
                if child is not None and child.role in ("statictext", "heading", "image") and (child.name or _text(child.value)):
                    node.name = child.name or _text(child.value)
                    break
        if not node.name and node.placeholder:
            node.name = node.placeholder                                 # LAW-TXT-7: empty field's name = placeholder


def region(node: Node, window: Rect | None) -> str:
    c = node.center
    if c is None or window is None:
        return "unknown"
    wx, wy, ww, wh = window
    if ww <= 0 or wh <= 0:
        return "unknown"
    cx, cy = c
    if cy - wy < min(0.12 * wh, 110):
        return "toolbar"
    if wy + wh - cy < min(0.08 * wh, 60):
        return "footer"
    h = node.bounds[3] if node.bounds else 0
    if cx - wx < min(0.25 * ww, 320) and h < 0.9 * wh:
        return "sidebar"
    if wx + ww - cx < min(0.25 * ww, 320) and h < 0.9 * wh:
        return "right"
    return "content"


def fill_regions(snap: Snapshot) -> None:
    kind = snap.root_kind
    for node in snap.iter():
        if kind in ("sheet", "popover", "menu"):
            node.region = kind
        else:
            node.region = region(node, snap.window_bounds)


def position_in_list(node: Node, snap: Snapshot) -> str:
    """'row 3/11' for items directly inside list-like containers."""
    parent = snap.node(node.parent)
    if parent is None or parent.role not in ("list", "table", "outline", "grid", "group"):
        return ""
    siblings = [c for c in parent.children if c in snap.nodes]
    if len(siblings) < 2:
        return ""
    try:
        i = siblings.index(node.alias)
    except ValueError:
        return ""
    total = max(parent.children_total, len(siblings))
    return f"row {i + 1}/{total}"
