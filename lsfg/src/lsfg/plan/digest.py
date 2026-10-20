"""The screen digest: what the planner sees, one line per element (implementation.md §6.10).

≤ 150 lines, about 15 tokens each. Interactive nodes, headings, the focused node, web areas
(with url=), and a few static texts. Aliases (@e12) let the plan point at elements in ~2 tokens.
Denylisted apps get a header only.
"""
from __future__ import annotations

from ..ax import caps
from ..ax.labels import label, position_in_list
from ..resolve.selector import id_tier
from ..types import Node, Snapshot

MAX_LINES = 150
MAX_STATIC = 30


def _flags(n: Node) -> str:
    keep = [s for s in ("focused", "selected", "checked", "expanded", "disabled", "offscreen") if s in n.states]
    return f"  ({', '.join(keep)})" if keep else ""


CONTAINERS = frozenset({"webarea", "scrollarea", "group", "list", "table", "outline", "window", "dialog", "sheet"})


def line_for(n: Node, snap: Snapshot, unique_ids: set[str] | None = None) -> str:
    text = label(n, snap)[:60]
    out = f"@{n.alias:<5} {n.role} {_q(text)}"
    v = n.value
    if isinstance(v, str) and v.strip() and v.strip()[:40] != text[:40]:
        out += f"  ={_q(v.strip()[:40])}"
    if n.role == "textfield" and not (isinstance(v, str) and v) and n.placeholder and n.placeholder != text:
        out += f"  ph={_q(n.placeholder[:40])}"
    ok_ids = unique_ids if unique_ids is not None else {n.identifier, n.dom_id}
    if n.identifier and id_tier(n.identifier) in ("high", "session") and n.identifier in ok_ids:
        out += f"  #{n.identifier[:48]}"
    elif n.dom_id and id_tier(n.dom_id) in ("high", "session") and n.dom_id in ok_ids:
        out += f"  dom#{n.dom_id[:48]}"
    if n.role == "webarea" and n.url:
        out += f"  url={n.url[:80]}"
    where = n.region if n.region != "unknown" and n.role not in CONTAINERS else ""
    pos = position_in_list(n, snap)
    if where or pos:
        out += f"  [{' '.join(x for x in (where, pos) if x)}]"
    return out + _flags(n)


def _q(s: str) -> str:
    return '"' + s.replace('"', "'") + '"'


def build(snap: Snapshot, *, framework: str = "", denied: bool = False,
          max_lines: int = MAX_LINES, keep: str = "") -> tuple[str, set[str]]:
    head = (f"SCREEN {snap.app_name} · window {_q(snap.window_title[:60])} · stack {snap.stack} · "
            f"{snap.readiness} · {len(snap.nodes)} nodes")
    if denied:
        return head + "\n(private app: no screen content is shared)", set()
    lines: list[str] = []
    aliases: set[str] = set()
    statics = 0
    from collections import Counter
    counts = Counter(x for n in snap.iter() for x in (n.identifier, n.dom_id) if x)
    unique_ids = {k for k, c in counts.items() if c == 1}     # only ids that pick exactly one element
    shown: dict[str, tuple[str, str]] = {}
    for n in snap.iter():
        if len(lines) >= max_lines:
            lines.append(f"… {len(snap.nodes) - len(aliases)} more nodes not shown")
            break
        if n.zero_area or "hidden" in n.states:
            continue
        include = False
        if n.role in ("webarea", "heading", "tablist") or "focused" in n.states:
            include = n.role != "group" or bool(label(n, snap))
        elif n.role == "statictext":
            parent = snap.node(n.parent)
            if statics < MAX_STATIC and label(n, snap) and parent is not None and parent.role not in ("button", "link", "cell", "row"):
                include = True
                statics += 1
        elif (n.name or n.value not in (None, "") or n.role in caps.INTERACTIVE_ROLES) and \
                caps.interactive(n, framework or snap.framework):
            include = True
        if include and _nested_duplicate(n, snap, shown):
            include = False                                    # <a><a>Home</a></a>: show one
        if include:
            lines.append(line_for(n, snap, unique_ids))
            aliases.add(n.alias)
            shown[n.alias] = (n.role, label(n, snap))
    from ..safety.redact import scrub
    return scrub(head + "\n" + "\n".join(lines), keep), aliases


def _nested_duplicate(n: Node, snap: Snapshot, shown: dict[str, tuple[str, str]]) -> bool:
    me = (n.role, label(n, snap))
    if not me[1]:
        return False
    for anc in snap.ancestors(n.alias)[:3]:
        if shown.get(anc.alias) == me:
            return True
    return False
