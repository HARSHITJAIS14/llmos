"""The resolution chain and waiting for a target (implementation.md §8.2–8.4; LAW-ID-12).

More than one match is always Ambiguous, never "take the first" (LAW-ID-7). Waiting for a
target to appear is how we wait for UI to load: no blind sleeps.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ..types import Node, Selector, Snapshot
from ..ax import raw, windows
from .selector import matches_clause


@dataclass
class Resolution:
    kind: str                                   # FOUND | NOT_FOUND | AMBIGUOUS
    node: Node | None = None
    matches: list[Node] = field(default_factory=list)
    snapshot: Snapshot | None = None
    detail: str = ""

    @property
    def found(self) -> bool:
        return self.kind == "FOUND"


def _usable(n: Node) -> bool:
    return not n.zero_area and "hidden" not in n.states


def resolve_in(sel: Selector, snap: Snapshot, session=None) -> Resolution:
    if sel.special == "chosen":
        n = session.bindings.get("chosen") if session else None
        if n is not None and snap.nodes.get(n.alias) is not None:
            return Resolution("FOUND", snap.nodes[n.alias], snapshot=snap)
        return Resolution("FOUND", n, snapshot=snap) if n is not None else Resolution("NOT_FOUND", snapshot=snap, detail="no @chosen binding")
    if sel.special and sel.special.startswith("alias:"):
        alias = sel.special.split(":", 1)[1]
        n = snap.nodes.get(alias)
        if n is not None:
            return Resolution("FOUND", n, snapshot=snap)
        stored = session.bindings.get("alias_selectors", {}).get(alias) if session else None
        if stored is not None:
            return resolve_in(stored, snap, session)
        return Resolution("NOT_FOUND", snapshot=snap, detail=f"@{alias} is not on screen any more")
    if sel.special == "focused":
        return _focused(snap, session)
    pool = list(snap.iter())
    for clause in sel.scope:
        hits = [n for n in pool if matches_clause(n, clause, snap)]
        if len(hits) != 1:
            kind = "NOT_FOUND" if not hits else "AMBIGUOUS"
            return Resolution(kind, matches=hits, snapshot=snap, detail="scope clause did not match exactly one node")
        pool = snap.subtree(hits[0].alias)[1:]
    hits = [n for n in pool if matches_clause(n, sel.target, snap) and _usable(n)]
    if sel.target.nth is not None:
        hits = hits[sel.target.nth:sel.target.nth + 1]
    if len(hits) == 1:
        return Resolution("FOUND", hits[0], matches=hits, snapshot=snap)
    if not hits:
        return Resolution("NOT_FOUND", snapshot=snap)
    return Resolution("AMBIGUOUS", matches=hits, snapshot=snap)


def _focused(snap: Snapshot, session=None) -> Resolution:
    err, ref = raw.attr(raw.app_element(snap.pid), "AXFocusedUIElement")
    if not raw.is_ref(ref):
        return Resolution("NOT_FOUND", snapshot=snap, detail="nothing has keyboard focus")
    for n in snap.iter():
        if n.ref is not None and raw.cf_equal(n.ref, ref):
            return Resolution("FOUND", n, snapshot=snap)
    # Focused element outside the walked tree (e.g. a popover field): make a node for it.
    from ..ax.identity import AliasTable
    from ..ax.walker import ATTRS_WITH_BOUNDS, make_node
    e, attrs = raw.batch(ref, ATTRS_WITH_BOUNDS)
    if e != raw.OK or not attrs.get("AXRole"):
        return Resolution("NOT_FOUND", snapshot=snap, detail="focused element unreadable")
    aliases = session.aliases if session is not None else AliasTable()
    node = make_node(ref, attrs, 0, None, snap.pid, aliases, 0.5)
    if not node.name and node.placeholder:
        node.name = node.placeholder
    return Resolution("FOUND", node, snapshot=snap)


def _still_there(node: Node) -> bool:
    """One batch read: the element is alive and keeps its role and label."""
    if node.ref is None:
        return False
    err, a = raw.batch(node.ref, ["AXRole", "AXTitle", "AXDescription", "AXValue", "AXIdentifier",
                                  "AXDOMIdentifier", "AXHidden"])
    if err != raw.OK or not a.get("AXRole"):
        return False
    if a.get("AXHidden") is True:
        return False
    if node.identifier and a.get("AXIdentifier") not in (None, node.identifier):
        return False
    if node.dom_id and a.get("AXDOMIdentifier") not in (None, node.dom_id):
        return False
    return True


def resolve(session, ctx, sel: Selector, *, fresh: bool = True, deep: bool = False,
            include_transient: bool = True) -> Resolution:
    last = session.last.get(ctx.pid) if ctx.pid is not None else None
    if last is not None and not deep and not sel.special and time.time() - last.captured_at < 30:
        quick = resolve_in(sel, last, session)                 # validated cache hit: 1 IPC, no walk
        if quick.kind == "FOUND" and _still_there(quick.node):
            return quick
    snap = session.observe(ctx, deep=deep) if fresh or last is None else last
    res = resolve_in(sel, snap, session)
    if res.kind == "NOT_FOUND" and include_transient and not sel.special:
        for surface in windows.transient_surfaces(snap.pid):     # open menus, popovers
            sub = session.observe(ctx, root_ref=surface)
            r2 = resolve_in(sel, sub, session)
            if r2.kind != "NOT_FOUND":
                return r2
    return res


def resolve_wait(session, ctx, sel: Selector, timeout: float) -> Resolution:
    """Poll until the selector resolves (16 ms growing ×1.5 to 100 ms). The last try goes deep."""
    deadline = time.monotonic() + timeout
    delay = 0.016
    res = Resolution("NOT_FOUND")
    while True:
        session.check()
        res = resolve(session, ctx, sel)
        if res.kind in ("FOUND", "AMBIGUOUS"):
            return res
        if time.monotonic() >= deadline:
            break
        time.sleep(delay)
        delay = min(0.1, delay * 1.5)
    deep = resolve(session, ctx, sel, deep=True)             # one deeper, bigger look before giving up
    return deep if deep.kind != "NOT_FOUND" else res


def ref_alive(ref: Any) -> bool:
    err, _ = raw.attr(ref, "AXRole")
    return err == raw.OK
