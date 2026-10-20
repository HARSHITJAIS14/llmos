"""Clean candidate lists before JEV sees them (implementation.md §12.2; reasoning.md D11, D28).

JEV is weak with large irrelevant state and can only pick what we offer, so the list is
filtered with the codex rules, ranked by relevance to the step, capped, and always has NONE.
"""
from __future__ import annotations

import re

from ..ax import caps, classify
from ..ax.labels import label, position_in_list
from ..ax.normalize import fold
from ..safety import policy
from ..types import Node, Snapshot

_WORD = re.compile(r"[a-z0-9]+")


def _eligible(n: Node, snap: Snapshot, framework: str, typing: bool) -> bool:
    if n.zero_area or "hidden" in n.states:                     # LAW-ID-7
        return False
    if not caps.actionable(n, framework):                       # LAW-ACT-7
        return False
    if "offscreen" in n.states and not caps.cap(n, "ScrollTo"):  # LAW-ACT-11
        return False
    if typing:
        in_web = snap.in_web(n.alias) if n.alias in snap.nodes else False
        return caps.typeable(n, classify.node_stack(framework, in_web))  # LAW-ACT-8, ACT-9, TXT-11
    if not label(n, snap).strip() and n.role not in ("textfield", "checkbox", "switch", "radiobutton"):
        return False
    return caps.clickable(n, framework)                         # never AXShowMenu alone (LAW-ACT-6)


def _expand(pool: list[Node], snap: Snapshot, framework: str) -> list[Node]:
    out: list[Node] = []
    seen: set[str] = set()
    for n in pool:
        members = [n]
        if n.role in caps.CONTAINER_ROLES or (n.children and not caps.clickable(n, framework)):
            members = snap.subtree(n.alias)[1:]
        for m in members:
            if m.alias not in seen:
                seen.add(m.alias)
                out.append(m)
    return out


def score(n: Node, snap: Snapshot, query_words: set[str], phrase: str) -> float:
    text = fold(label(n, snap) + " " + (n.value if isinstance(n.value, str) else ""))
    words = set(_WORD.findall(text))
    s = 0.0
    if phrase and phrase == fold(label(n, snap)):
        s += 5.0
    if phrase and phrase in text:
        s += 2.0
    s += 1.0 * len(words & query_words)
    s += 0.5 * sum(1 for q in query_words if any(w.startswith(q) for w in words))
    return s


def rank(nodes: list[Node], snap: Snapshot, want: str, extra: list[str] | None = None) -> list[Node]:
    query = fold(" ".join([want] + (extra or [])))
    words = {w for w in _WORD.findall(query) if len(w) > 1}
    phrase = fold(extra[0]) if extra else ""
    indexed = list(enumerate(nodes))
    indexed.sort(key=lambda t: (-score(t[1], snap, words, phrase), t[0]))
    return [n for _, n in indexed]


def candidates_for(pool: list[Node], snap: Snapshot, ctx, want: str, *, typing: bool = False,
                   keep: int = 60, cap_n: int = 200, drop_irreversible: bool = False,
                   extra: list[str] | None = None) -> list[Node]:
    nodes = [n for n in _expand(pool, snap, ctx.framework) if _eligible(n, snap, ctx.framework, typing)]
    if drop_irreversible:
        nodes = [n for n in nodes if not policy.label_looks_irreversible(label(n, snap))]
    seen: set[tuple] = set()
    uniq = []
    for n in nodes:                                             # merge exact duplicates
        k = (n.role, fold(label(n, snap)), tuple(round(v) for v in n.bounds) if n.bounds else None)
        if k not in seen:
            seen.add(k)
            uniq.append(n)
    uniq = _drop_nested_repeats(uniq, snap)
    ranked = rank(uniq, snap, want, extra)
    return ranked[:min(keep, cap_n)]


def _drop_nested_repeats(nodes: list[Node], snap: Snapshot) -> list[Node]:
    """A row and its own text are one choice, not two. Offering both split JEV's confidence
    (live, WhatsApp: group#ChatListSearchView_ContactResult and its statictext, 0.53 < 0.60).
    Keep the outer, actionable one."""
    chosen = {n.alias for n in nodes}
    out = []
    for n in nodes:
        mine = fold(label(n, snap))
        anc, hops, repeat = n.parent, 0, False
        while anc and hops < 3 and mine:
            a = snap.nodes.get(anc)
            if a is None:
                break
            if anc in chosen and fold(label(a, snap)) == mine:
                repeat = True
                break
            anc, hops = a.parent, hops + 1
        if not repeat:
            out.append(n)
    return out


def all_candidates(snap: Snapshot, ctx, want: str, **kw) -> list[Node]:
    root = snap.root()
    pool = [root] if root is not None else []
    if ctx.framework in ("electron", "cef") and snap.webareas():
        pool = snap.webareas() + [n for n in snap.iter() if n.depth <= 1]   # LAW-STR-2
    return candidates_for(pool, snap, ctx, want, **kw)


def describe(n: Node, snap: Snapshot, mask=None, keep: str = "") -> dict:
    from ..safety.redact import scrub
    lab = scrub(label(n, snap)[:80], keep)
    d: dict = {"role": n.role, "label": mask(lab) if mask else lab}
    if n.identifier and len(n.identifier) <= 48 and re.fullmatch(r"[A-Za-z][A-Za-z_.:-]*", n.identifier):
        d["id"] = n.identifier                   # e.g. ChatListSearchView_ContactResult vs _MessageResult
    v = n.value
    if isinstance(v, str) and v.strip() and v.strip()[:80] != lab:
        vv = scrub(v.strip()[:80], keep)
        d["value"] = mask(vv) if mask else vv
    where = " ".join(x for x in (n.region if n.region != "unknown" else "", position_in_list(n, snap)) if x)
    if where:
        d["where"] = where
    flags = [s for s in ("selected", "checked", "focused", "expanded") if s in n.states]
    if flags:
        d["state"] = ",".join(flags)
    return d
