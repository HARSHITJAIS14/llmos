"""Trace → route template, deterministically (implementation.md §14.5; reasoning.md D18).

Every free-text literal (typed text, a choose target, a URL query) must be a contiguous span of
the task, or it is not compiled: guessing would replay the old literal on a new task
("typed Get Lucky Daft Punk" for "play blinding lights"). Aliases are replaced by the stored
selectors the planner bound at accept time; refs and aliases never reach a route (LAW-ID-8).
"""
from __future__ import annotations

import re
import urllib.parse

from ..ax.normalize import fold
from ..resolve.selector import fmt
from ..router import normalize_task
from ..types import Step
from .schema import OPS

SLOT_NAMES = {"type": "text", "choose": "item", "open_url": "q", "explore": "text"}


def _alias_to_selector(value: str, table: dict) -> str | None:
    if isinstance(value, str) and re.fullmatch(r"@e\d+", value):
        sel = table.get(value[1:])
        return fmt(sel) if sel is not None else None
    return value


def compile_route(task: str, steps: list[Step], alias_table: dict) -> dict | None:
    """Returns {template, regex, slots, plan, literal_len} or None when it can't be done safely."""
    t = normalize_task(task)
    if not t or not steps:
        return None
    literals: list[tuple[str, str]] = []                       # (literal, slot kind)
    out_steps: list[dict] = []
    for s in steps:
        if s.op in ("ask", "explore", "route", "wait"):
            return None                                        # not replayable without a model/user
        d = {"op": s.op, "app": s.app, **s.params}
        for f in ("target", "among"):
            if f in d:
                sel = _alias_to_selector(d[f], alias_table)
                if sel is None:
                    return None
                d[f] = sel
        if s.op == "type":
            literals.append((str(d.get("text") or ""), "text"))
        elif s.op == "choose":
            literals.append((str(d.get("want") or ""), "item"))
        elif s.op == "open_url":
            q = urllib.parse.urlparse(str(d.get("url") or "")).query
            for _, v in urllib.parse.parse_qsl(q):
                literals.append((v, "q"))
        if "risk" in OPS[s.op]:
            d["risk"] = s.risk
        pre, post = [], []
        for c in s.pre + s.post:
            cd = {"k": c.kind, "app": c.app, **c.params, "g": c.group}
            if "target" in cd:
                sel = _alias_to_selector(cd["target"], alias_table)
                if sel is None:
                    return None
                cd["target"] = sel
            (pre if c.when == "pre" else post).append(cd)
        d["pre"], d["post"] = pre, post
        out_steps.append(d)

    template = t
    slots: list[dict] = []
    subs: dict[str, str] = {}
    for lit, kind in literals:
        f = fold(lit).strip()
        if not f:
            continue
        if f in subs:
            continue
        m = re.search(r"(?<![a-z0-9])" + re.escape(f) + r"(?![a-z0-9])", template)
        if m is None:
            if kind != "item":
                return None                                    # typed text / URL query must be a clean task span
            # A choose `want` is usually a description ("the chat titled X"): slot its quoted or
            # longest task-matching part; if there is none, it stays a runtime JEV decision.
            inner = _inner_literal(lit, template)
            if inner is None:
                continue
            f = inner
            m = re.search(r"(?<![a-z0-9])" + re.escape(f) + r"(?![a-z0-9])", template)
            if m is None:
                continue
        name = f"s{len(slots) + 1}"
        slots.append({"key": name, "kind": kind})
        subs[f] = name
        template = template[:m.start()] + "{" + name + "}" + template[m.end():]
    if not slots and literals and any(k == "text" for _, k in literals):
        return None
    plan = {"steps": [_replace_literals(d, subs) for d in out_steps]}
    regex = _regex(template)
    literal_len = len(re.sub(r"\{s\d+\}", "", template))
    return {"template": template, "regex": regex, "slots": slots, "plan": plan, "literal_len": literal_len}


def _inner_literal(lit: str, template: str) -> str | None:
    for m in re.finditer(r"['\"“‘]([^'\"”’]+)['\"”’]", lit):
        f = fold(m.group(1)).strip()
        if f and f in template:
            return f
    words = fold(lit).split()
    for n in range(len(words), 0, -1):                          # longest run of words found in the task
        for i in range(len(words) - n + 1):
            chunk = " ".join(words[i:i + n])
            if len(chunk) >= 3 and re.search(r"(?<![a-z0-9])" + re.escape(chunk) + r"(?![a-z0-9])", template):
                return chunk
    return None


def _replace_literals(obj, subs: dict[str, str]):
    if isinstance(obj, str):
        out = obj
        for lit, name in sorted(subs.items(), key=lambda kv: -len(kv[0])):
            out = re.sub(re.escape(lit), "{" + name + "}", out, flags=re.I)
            enc = urllib.parse.quote_plus(lit)
            if enc != lit:
                out = re.sub(re.escape(enc), "{" + name + ":url}", out, flags=re.I)
            esc = re.escape(lit)
            if esc != lit:
                out = out.replace(esc, "{" + name + ":re}")
        return out
    if isinstance(obj, list):
        return [_replace_literals(x, subs) for x in obj]
    if isinstance(obj, dict):
        return {k: _replace_literals(v, subs) for k, v in obj.items()}
    return obj


def _regex(template: str) -> str:
    parts = re.split(r"(\{s\d+\})", template)
    rx = ""
    for p in parts:
        m = re.fullmatch(r"\{(s\d+)\}", p)
        rx += f"(?P<{m.group(1)}>.+?)" if m else re.escape(p)
    return "^" + rx + "$"
