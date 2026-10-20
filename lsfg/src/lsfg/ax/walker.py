"""The budgeted AX walk (implementation.md §6.3).

One batch call per node. An explicit stack, so the deadline is checked at every node
(arc-cua's recursive walk only checked it at the root: reasoning.md B4). Depth by stack:
native trees never go below depth 9 (LAW-STR-3); web content goes to depth 30 and a
depth-10 cap cuts it silently (LAW-STR-6, LIFE-1), so web walks go to 45 and anything
cut is recorded as a frontier we can continue from without re-walking the top.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any

from ..types import Node, Snapshot
from . import raw
from .identity import AliasTable
from .labels import fill_child_labels, fill_regions, label
from .normalize import base_name, coerce_value, norm, normalize_role, placeholder_of, states_from

ATTRS = [
    "AXRole", "AXSubrole", "AXTitle", "AXDescription", "AXValue", "AXEnabled", "AXFocused",
    "AXSelected", "AXExpanded", "AXHidden", "AXElementBusy", "AXModal", "AXRequired",
    "AXIdentifier", "AXDOMIdentifier", "AXLabelValue", "AXPlaceholderValue", "AXTitleUIElement",
    "AXHelp", "AXURL", "AXChildren", "AXVisibleChildren", "AXVisibleRows",
    "AXVerticalScrollBar", "AXHorizontalScrollBar",
]
ATTRS_WITH_BOUNDS = ATTRS + ["AXPosition", "AXSize"]

LEAF_ROLES = frozenset({"statictext", "image", "separator", "splitter", "progressbar", "handle",
                        "scrollbar", "levelindicator", "relevanceindicator"})
LIST_LIKE = frozenset({"list", "table", "outline", "grid", "browser"})


@dataclass(slots=True)
class Budget:
    max_depth: int
    max_nodes: int
    deadline_ms: int
    fanout_cap: int
    fanout_keep: int
    bounds: bool
    call_timeout: float = 0.5


def budget_for(stack: str, *, slow_ax: bool = False) -> Budget:
    if stack == "web":
        return Budget(45, 3000, 1500, 80, 60, True)
    if stack == "qt":
        return Budget(12, 1500, 700, 60, 40, False)
    if stack == "opaque":
        return Budget(2, 50, 200, 60, 40, False)
    return Budget(12, 1500, 700, 60, 40, not slow_ax)


def _str(v: Any) -> str:
    return v if isinstance(v, str) else ""


def make_node(ref: Any, attrs: dict, depth: int, parent: str | None, pid: int,
              aliases: AliasTable, timeout: float) -> Node:
    alias, key = aliases.alias(pid, ref)
    subrole = _str(attrs.get("AXSubrole")) or None
    role = normalize_role(_str(attrs.get("AXRole")), subrole)
    value, vlen = coerce_value(attrs.get("AXValue"))
    title_text = ""
    title_ref = attrs.get("AXTitleUIElement")
    if raw.is_ref(title_ref) and not norm(_str(attrs.get("AXLabelValue"))):
        err, ta = raw.batch(title_ref, ["AXValue", "AXTitle"], timeout)   # rare: labeled form fields
        title_text = _str(ta.get("AXValue")) or _str(ta.get("AXTitle"))
    pos, size = attrs.get("AXPosition"), attrs.get("AXSize")
    bounds = (pos[0], pos[1], size[0], size[1]) if pos and size else None
    node = Node(
        alias=alias, key=key, ref=ref, role=role, subrole=subrole,
        name=base_name(attrs, role, title_text), value=value, value_len=vlen,
        description=norm(_str(attrs.get("AXDescription"))), help=norm(_str(attrs.get("AXHelp")))[:300],
        placeholder=placeholder_of(attrs), identifier=_str(attrs.get("AXIdentifier")),
        dom_id=_str(attrs.get("AXDOMIdentifier")), url=_str(attrs.get("AXURL")),
        states=states_from(attrs, role, subrole, attrs.get("AXValue")), bounds=bounds,
        depth=depth, parent=parent, title_ref=title_ref if raw.is_ref(title_ref) else None,
    )
    if raw.is_ref(attrs.get("AXVerticalScrollBar")) or raw.is_ref(attrs.get("AXHorizontalScrollBar")):
        node.caps["_scrollbars"] = True
    return node


def walk(snap: Snapshot, root_ref: Any, aliases: AliasTable, budget: Budget, *,
         depth0: int = 0, parent: str | None = None, skip_ax_roles: frozenset = frozenset()) -> str | None:
    """Walk from root_ref into `snap`. Returns the alias of the first node added."""
    t0 = time.perf_counter()
    deadline = t0 + budget.deadline_ms / 1000.0
    attrs_list = ATTRS_WITH_BOUNDS if budget.bounds else ATTRS
    stack: list[tuple[Any, int, str | None]] = [(root_ref, depth0, parent)]
    timeouts = 0
    first: str | None = None
    while stack:
        now = time.perf_counter()
        if now > deadline:
            snap.truncated.add("deadline")
            break
        if len(snap.nodes) >= budget.max_nodes:
            snap.truncated.add("nodes")
            break
        ref, depth, par = stack.pop()
        err, attrs = raw.batch(ref, attrs_list, timeout=min(budget.call_timeout, max(0.05, deadline - now)))
        if err == raw.INVALID_UI_ELEMENT:
            continue                                         # died mid-walk
        if err == raw.CANNOT_COMPLETE:
            timeouts += 1
            if timeouts >= 3:
                snap.truncated.add("app_busy")
                break
            continue
        if err != raw.OK or not attrs.get("AXRole"):
            continue
        if attrs.get("AXRole") in skip_ax_roles:
            continue
        node = make_node(ref, attrs, depth, par, snap.pid, aliases, budget.call_timeout)
        if node.alias in snap.nodes:
            continue                                         # the same element reached twice
        snap.nodes[node.alias] = node
        snap.order.append(node.alias)
        if par is not None and par in snap.nodes:
            snap.nodes[par].children.append(node.alias)
        if first is None:
            first = node.alias
        kids = [k for k in (attrs.get("AXChildren") or []) if raw.is_ref(k)]
        node.children_total = len(kids)
        if node.role in LEAF_ROLES:
            kids = []
        elif node.role in LIST_LIKE and len(kids) > budget.fanout_cap:
            visible = [k for k in (attrs.get("AXVisibleRows") or attrs.get("AXVisibleChildren") or [])
                       if raw.is_ref(k)]
            kids = visible[:budget.fanout_cap] if visible else kids[:budget.fanout_keep]
            snap.truncated.add("fanout")                     # LAW-STR-9/10, LIFE-7: never drill giant lists
        if kids and depth >= budget.max_depth:
            snap.frontier.append(node.alias)                 # the depth-cap signal (LAW-STR-6)
            continue
        for k in reversed(kids):
            stack.append((k, depth + 1, node.alias))
    snap.timings_ms["walk"] = snap.timings_ms.get("walk", 0) + round((time.perf_counter() - t0) * 1000)
    return first


def continue_walk(snap: Snapshot, aliases: AliasTable, budget: Budget, extra_depth: int = 15) -> int:
    """Walk below frontier nodes (their refs are still valid). The shallow tree is an exact
    prefix of the deep one (LAW-LIFE-1), so nothing above the frontier is re-read."""
    frontier, snap.frontier = list(snap.frontier), []
    added = 0
    deeper = Budget(budget.max_depth + extra_depth, budget.max_nodes, budget.deadline_ms,
                    budget.fanout_cap, budget.fanout_keep, budget.bounds, budget.call_timeout)
    for alias in frontier:
        node = snap.nodes.get(alias)
        if node is None or node.ref is None:
            continue
        err, attrs = raw.batch(node.ref, ["AXChildren"])
        before = len(snap.nodes)
        for k in [k for k in (attrs.get("AXChildren") or []) if raw.is_ref(k)]:
            walk(snap, k, aliases, deeper, depth0=node.depth + 1, parent=alias)
        added += len(snap.nodes) - before
    if snap.root_alias:
        snap.order = [n.alias for n in snap.subtree(snap.root_alias)]
    return added


def post_pass(snap: Snapshot) -> None:
    fill_child_labels(snap)
    fill_regions(snap)
    snap.signature = signature(snap.iter(), snap)


def signature(nodes, snap: Snapshot | None = None) -> str:
    """Change signature. Stable aliases make it equal on an idle UI. Never includes OCR."""
    h = hashlib.sha1()
    for n in nodes:
        v = n.value if not isinstance(n.value, str) else n.value[:60]
        h.update(f"{n.alias}|{n.role}|{label(n, snap)[:60]}|{v}|{','.join(sorted(n.states))}\n".encode())
    return h.hexdigest()[:16]


def shallow_signature(pid: int, root_ref: Any, aliases: AliasTable, max_depth: int = 5,
                      max_nodes: int = 80) -> str:
    """Cheap 'did anything change?' probe for wait_quiet (implementation.md §10)."""
    snap = Snapshot(pid=pid, bundle_id="", app_name="", framework="", stack="")
    walk(snap, root_ref, aliases, Budget(max_depth, max_nodes, 250, 40, 20, False))
    return signature(snap.iter())
