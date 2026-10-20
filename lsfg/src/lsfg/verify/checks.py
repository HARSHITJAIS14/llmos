"""The closed list of check kinds and their validation (implementation.md §11.1).

Rules: no empty patterns (atree's title_matches once matched everything on ""), patterns
must compile, typed text is checked via value (never the label, LAW-TXT-7).
"""
from __future__ import annotations

import re

from ..types import Check

KINDS: dict[str, tuple[str, ...]] = {
    "frontmost": (),
    "running": (),
    "title": ("pattern",),
    "url": ("pattern",),
    "exists": ("target",),
    "absent": ("target",),
    "value": ("target", "op", "text"),
    "state": ("target", "state", "is"),
    "text": ("text", "region"),
    "menu_checked": ("path", "is"),
}
VALUE_OPS = ("equals", "contains", "regex", "empty", "not_empty")
STATES = ("checked", "selected", "focused", "expanded", "enabled")
TRIVIAL = ("frontmost", "running")
MAX_PATTERN = 200


def from_json(d: dict) -> Check:
    kind = str(d.get("k") or d.get("kind") or "")
    params = {f: d.get(f) for f in KINDS.get(kind, ())}
    return Check(kind=kind, app=str(d.get("app") or ""), params=params,
                 group=int(d.get("g", 0) or 0), when=str(d.get("when") or "post"))


def validate(check: Check) -> list[str]:
    errs: list[str] = []
    if check.kind not in KINDS:
        return [f"unknown check kind {check.kind!r}"]
    if not check.app:
        errs.append(f"{check.kind}: app is required")
    p = check.params
    for f in KINDS[check.kind]:
        if f not in p or p[f] is None:
            errs.append(f"{check.kind}: {f} is required")
    if check.kind in ("title", "url"):
        pat = p.get("pattern") or ""
        if not str(pat).strip():
            errs.append(f"{check.kind}: empty pattern would match everything")
        elif len(pat) > MAX_PATTERN:
            errs.append(f"{check.kind}: pattern longer than {MAX_PATTERN} chars")
        else:
            try:
                re.compile(pat)
            except re.error as e:
                errs.append(f"{check.kind}: bad regex {pat!r}: {e}")
    if check.kind == "value":
        op = p.get("op")
        if op not in VALUE_OPS:
            errs.append(f"value: op must be one of {VALUE_OPS}")
        elif op in ("equals", "contains", "regex") and not str(p.get("text") or "").strip():
            errs.append("value: empty text would match everything")
        elif op == "regex":
            try:
                re.compile(p.get("text") or "")
            except re.error as e:
                errs.append(f"value: bad regex: {e}")
    if check.kind == "state" and p.get("state") not in STATES:
        errs.append(f"state: state must be one of {STATES}")
    if check.kind == "text" and not str(p.get("text") or "").strip():
        errs.append("text: empty text would match everything")
    if check.kind == "menu_checked" and not p.get("path"):
        errs.append("menu_checked: path is required")
    if check.when not in ("pre", "post"):
        errs.append(f"{check.kind}: when must be pre or post")
    return errs


def groups(checks: list[Check]) -> dict[int, list[Check]]:
    out: dict[int, list[Check]] = {}
    for c in checks:
        out.setdefault(c.group, []).append(c)
    return out


def describe(check: Check) -> str:
    p = check.params
    if check.kind in ("frontmost", "running"):
        return f"{check.kind}({check.app})"
    if check.kind in ("title", "url"):
        return f"{check.kind}({check.app}) ~ /{p.get('pattern')}/"
    if check.kind == "value":
        return f"value({p.get('target')}) {p.get('op')} {p.get('text')!r}"
    if check.kind == "state":
        return f"state({p.get('target')}).{p.get('state')} is {p.get('is')}"
    if check.kind == "text":
        return f"text({check.app}) has {p.get('text')!r}"
    if check.kind == "menu_checked":
        return f"menu {' > '.join(p.get('path') or [])} checked is {p.get('is')}"
    return f"{check.kind}({p.get('target')})"
