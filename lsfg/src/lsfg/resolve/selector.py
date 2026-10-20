"""The selector grammar (implementation.md §8.1).

    selector := special | clause ( ">" clause )*
    special  := "focused" | "@chosen" | "@e" DIGITS
    clause   := [role] ( "#" IDENT ["*"] | "dom#" IDENT | ":" QUOTED | "~" QUOTED | "=" QUOTED )? [ "[" INT "]" ]

Stored selectors never contain aliases or refs (LAW-ID-8). from_node() turns a live node into
the most stable selector the codex identity laws allow (ID-1..3, ID-6, ID-12).
"""
from __future__ import annotations

import re

from ..errors import PlanInvalid
from ..types import Clause, Node, Selector, Snapshot
from ..ax.labels import label
from ..ax.normalize import fold

_ROLE_RE = re.compile(r"[a-z][a-z0-9_]*")
_IDENT_RE = re.compile(r"[^\s>\[\]\"]+")


class SelectorError(PlanInvalid):
    pass


def _quoted(s: str, i: int) -> tuple[str, int]:
    if i >= len(s) or s[i] != '"':
        raise SelectorError(f"expected a quoted string at column {i + 1}: {s!r}")
    out = []
    i += 1
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            out.append(s[i + 1])
            i += 2
            continue
        if ch == '"':
            return "".join(out), i + 1
        out.append(ch)
        i += 1
    raise SelectorError(f"unterminated quote in {s!r}")


def _ident_at(s: str, i: int, what: str) -> tuple[str, bool, int]:
    """IDENT or "quoted id" (ids may hold spaces, e.g. Calendar's 'previous day'), then an optional '*'."""
    if i < len(s) and s[i] == '"':
        text, i = _quoted(s, i)
    else:
        m = _IDENT_RE.match(s, i)
        if not m:
            raise SelectorError(f"expected {what} at column {i + 1}: {s!r}")
        text, i = m.group(0), m.end()
        if text.endswith("*"):
            return text[:-1], True, i
    if i < len(s) and s[i] == "*":
        return text, True, i + 1
    return text, False, i


def _clause(s: str, i: int) -> tuple[Clause, int]:
    role = None
    m = _ROLE_RE.match(s, i)
    if m and not s.startswith("dom#", i):
        word = m.group(0)
        if word.endswith("dom") and s.startswith("#", m.end()):     # "groupdom#root" = group + dom#root
            role, i = (word[:-3] or None), m.end() - 3
        else:
            role, i = word, m.end()
    ident = dom_id = name = value = None
    ident_prefix = False
    name_mode = "exact"
    if s.startswith("dom#", i):
        dom_id, _, i = _ident_at(s, i + 4, "a DOM id")
    elif i < len(s) and s[i] == "#":
        ident, ident_prefix, i = _ident_at(s, i + 1, "an identifier")
    elif i < len(s) and s[i] in ":~=":
        op = s[i]
        text, i = _quoted(s, i + 1)
        if op == "=":
            value = text
        else:
            name, name_mode = text, ("contains" if op == "~" else "exact")
    nth = None
    if i < len(s) and s[i] == "[":
        j = s.find("]", i)
        if j < 0 or not s[i + 1:j].strip().isdigit():
            raise SelectorError(f"bad [n] at column {i + 1}: {s!r}")
        nth, i = int(s[i + 1:j]), j + 1
    if role is None and ident is None and dom_id is None and name is None and value is None:
        raise SelectorError(f"empty selector clause at column {i + 1}: {s!r}")
    return Clause(role=role, ident=ident, ident_prefix=ident_prefix, dom_id=dom_id, name=name,
                  name_mode=name_mode, value=value, nth=nth), i


def parse(text: str) -> Selector:
    s = (text or "").strip()
    if not s:
        raise SelectorError("empty selector")
    if s == "focused":
        return Selector(special="focused")
    if s == "@chosen":
        return Selector(special="chosen")
    if re.fullmatch(r"@e\d+", s):
        return Selector(special="alias:" + s[1:])
    clauses: list[Clause] = []
    i = 0
    while True:
        while i < len(s) and s[i] == " ":
            i += 1
        c, i = _clause(s, i)
        clauses.append(c)
        while i < len(s) and s[i] == " ":
            i += 1
        if i >= len(s):
            break
        if s[i] != ">":
            raise SelectorError(f"unexpected {s[i]!r} at column {i + 1}: {s!r}")
        i += 1
    return Selector(scope=tuple(clauses[:-1]), target=clauses[-1])


def _q(t: str) -> str:
    return '"' + t.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _id(v: str) -> str:
    return v if _IDENT_RE.fullmatch(v) and not v.endswith("*") else _q(v)


def fmt_clause(c: Clause) -> str:
    out = c.role or ""
    if c.dom_id:
        out += "dom#" + _id(c.dom_id)
    elif c.ident:
        out += "#" + _id(c.ident) + ("*" if c.ident_prefix else "")
    elif c.name is not None:
        out += ("~" if c.name_mode == "contains" else ":") + _q(c.name)
    elif c.value is not None:
        out += "=" + _q(c.value)
    if c.nth is not None:
        out += f"[{c.nth}]"
    return out


def fmt(sel: Selector) -> str:
    if sel.special == "focused":
        return "focused"
    if sel.special == "chosen":
        return "@chosen"
    if sel.special and sel.special.startswith("alias:"):
        return "@" + sel.special.split(":", 1)[1]
    return ">".join(fmt_clause(c) for c in (*sel.scope, sel.target))


# ------------------------------------------------------------------- identity tiers

_REACT_ID = re.compile(r"^(:r[0-9a-z]+:|_r_[0-9a-z]+_|view_\d+)$")      # LAW-ID-3
_NS_ID = re.compile(r"^_NS:\d+$")                                        # LAW-ID-2 tier LOW
_UUID = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-")                    # LAW-ID-2 tier SESSION


def id_tier(ident: str) -> str:
    if not ident:
        return "none"
    if _REACT_ID.match(ident):
        return "volatile"
    if _NS_ID.match(ident):
        return "low"
    if _UUID.search(ident):
        return "session"
    return "high"


def _stable_prefix(ident: str) -> str | None:
    """'<component>?<query>' or '<component>:<payload>' → keep only the non-user prefix."""
    for sep in ("?", ":"):
        if sep in ident:
            head = ident.split(sep, 1)[0]
            if len(head) >= 4:
                return head + sep
    return None


def matches_clause(node: Node, c: Clause, snap: Snapshot | None = None) -> bool:
    if c.role and node.role != c.role:
        return False
    if c.ident is not None:
        if c.ident_prefix:
            if not node.identifier.startswith(c.ident):
                return False
        elif node.identifier != c.ident:
            return False
    if c.dom_id is not None and node.dom_id != c.dom_id:
        return False
    if c.name is not None:
        have = fold(label(node, snap))
        want = fold(c.name)
        if c.name_mode == "contains":
            if want not in have:
                return False
        elif have != want:
            return False
    if c.value is not None:
        v = node.value if isinstance(node.value, str) else ("" if node.value is None else str(node.value))
        if fold(v) != fold(c.value):
            return False
    return True


def _unique(nodes: list[Node], c: Clause, snap: Snapshot) -> bool:
    return sum(1 for n in nodes if matches_clause(n, c, snap) and not n.zero_area) == 1


def from_node(node: Node, snap: Snapshot) -> Selector:
    """The most stable stored selector for a live node (alias → selector conversion, §8.1)."""
    everything = list(snap.iter())
    tier = id_tier(node.identifier)
    if tier == "high":
        c = Clause(role=node.role, ident=node.identifier)
        if _unique(everything, c, snap):
            return Selector(target=c)
        pre = _stable_prefix(node.identifier)
        if pre:
            c = Clause(role=node.role, ident=pre, ident_prefix=True)
            if _unique(everything, c, snap):
                return Selector(target=c)
    elif tier == "session":
        pre = _stable_prefix(node.identifier)
        if pre:
            c = Clause(role=node.role, ident=pre, ident_prefix=True)
            if _unique(everything, c, snap):
                return Selector(target=c)
    if node.dom_id and id_tier(node.dom_id) in ("high", "session"):
        c = Clause(role=node.role, dom_id=node.dom_id)
        if _unique(everything, c, snap):
            return Selector(target=c)
    text = label(node, snap)
    if node.role == "textfield" and not node.name and isinstance(node.value, str) and node.value:
        c = Clause(role="textfield", value=node.value)            # identity lives in value (LAW-ID-4)
        if _unique(everything, c, snap):
            return Selector(target=c)
    if text:
        c = Clause(role=node.role, name=text)
        if _unique(everything, c, snap):
            return Selector(target=c)
        scope = _scope_for(node, snap)
        pool = snap.subtree(scope.alias) if scope else everything
        same = [n for n in pool if matches_clause(n, c, snap) and not n.zero_area]
        nth = next((i for i, n in enumerate(same) if n.alias == node.alias), None)
        sc = (_scope_clause(scope, snap),) if scope else ()
        if sc and sc[0] is not None:
            return Selector(scope=sc, target=Clause(role=node.role, name=text, nth=nth))
        return Selector(target=Clause(role=node.role, name=text, nth=nth))
    # Unnamed: index among same-role siblings under the nearest uniquely-named ancestor.
    scope = _scope_for(node, snap)
    pool = snap.subtree(scope.alias) if scope else everything
    same = [n for n in pool if n.role == node.role and not n.zero_area]
    nth = next((i for i, n in enumerate(same) if n.alias == node.alias), 0)
    sc = _scope_clause(scope, snap) if scope else None
    return Selector(scope=(sc,) if sc else (), target=Clause(role=node.role, nth=nth))


def _scope_for(node: Node, snap: Snapshot) -> Node | None:
    everything = list(snap.iter())
    for anc in snap.ancestors(node.alias):
        c = _scope_clause(anc, snap)
        if c is not None and _unique(everything, c, snap):
            return anc
    return None


def _scope_clause(node: Node | None, snap: Snapshot) -> Clause | None:
    if node is None:
        return None
    if node.identifier and id_tier(node.identifier) == "high":
        return Clause(role=node.role, ident=node.identifier)
    if node.dom_id and id_tier(node.dom_id) == "high":
        return Clause(role=node.role, dom_id=node.dom_id)
    text = label(node, snap)
    if text and node.role not in ("group", "statictext"):
        return Clause(role=node.role, name=text)
    return None
