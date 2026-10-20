"""Evaluating checks in code, and waiting on them (implementation.md §10, §11.2).

Cheapest read first: a cached ref (1 IPC) → a scoped/full walk. Same group = OR, different
groups = AND. UNVERIFIABLE counts as a failure. A model's claim of success is never a verdict.
"""
from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from ..act import apps
from ..ax import menu as menus
from ..ax import raw, windows
from ..ax.normalize import checked_value, fold, norm
from ..errors import AppNotFound, LsfgError
from ..resolve import resolver
from ..resolve.selector import SelectorError, parse
from ..types import Check
from .checks import describe, groups

ADDRESS_FIELDS = ('#WEB_BROWSER_ADDRESS_AND_SEARCH_FIELD', 'textfield~"Address and search"',
                  'textfield~"address bar"')


@dataclass
class CheckResult:
    kind: str
    ok: bool
    observed: Any = None
    unverifiable: bool = False
    detail: str = ""
    what: str = ""

    def to_json(self, store_text: bool = True) -> dict:
        obs = self.observed
        if not store_text and isinstance(obs, str):
            obs = f"<{len(obs)} chars>"
        return {"kind": self.kind, "ok": self.ok, "what": self.what, "observed": obs,
                "unverifiable": self.unverifiable, "detail": self.detail}


def _text(v: Any) -> str:
    if v is None:
        return ""                                   # LAW-TXT-1: a missing value means empty
    return norm(v) if isinstance(v, str) else str(v)


def _node_for(session, ctx, target: str):
    """Resolve a check target, reusing a live cached ref when possible (1 IPC instead of a walk)."""
    key = (ctx.pid, target)
    cache = session.bindings.setdefault("_ref_cache", {})
    node = cache.get(key)
    if node is not None and node.ref is not None and resolver.ref_alive(node.ref):
        return node, ""
    sel = parse(target)
    res = resolver.resolve(session, ctx, sel)
    if res.kind == "FOUND":
        cache[key] = res.node
        return res.node, ""
    if res.kind == "AMBIGUOUS":
        return None, f"{len(res.matches)} elements match {target}"
    return None, f"{target} not found"


def page_url(session, ctx) -> str:
    cache = session.bindings.setdefault("_webarea", {})
    ref = cache.get(ctx.pid)
    if ref is not None:
        err, url = raw.attr(ref, "AXURL")
        if err == raw.OK and isinstance(url, str) and url:
            return url
    win = windows.pick_window(ctx.pid)
    if win is not None:
        queue, seen = deque([win.ref]), 0
        while queue and seen < 800:
            r = queue.popleft()
            seen += 1
            err, a = raw.batch(r, ["AXRole", "AXURL", "AXChildren"])
            if a.get("AXRole") == "AXWebArea":
                cache[ctx.pid] = r
                url = a.get("AXURL")
                if isinstance(url, str) and url:
                    return url
                break
            queue.extend(k for k in (a.get("AXChildren") or []) if raw.is_ref(k))
    for sel in ADDRESS_FIELDS:                      # fallback: the address field's text
        try:
            node, _ = _node_for(session, ctx, sel)
        except (SelectorError, LsfgError):
            node = None
        if node is not None:
            err, v = raw.attr(node.ref, "AXValue")
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""


def evaluate(check: Check, session) -> CheckResult:
    k, p = check.kind, check.params
    r = CheckResult(kind=k, ok=False, what=describe(check))
    try:
        ctx = session.ctx(check.app)
    except AppNotFound as e:
        r.detail = str(e)
        return r
    if k == "frontmost":
        fm = apps.frontmost()
        r.observed = fm[2] if fm else None
        r.ok = fm is not None and fm[0] == ctx.bundle_id
        return r
    session._refresh_pid(ctx)
    if k == "running":
        r.ok = ctx.pid is not None
        return r
    if ctx.pid is None:
        r.detail = f"{ctx.name} is not running"
        return r
    try:
        if k == "title":
            win = windows.pick_window(ctx.pid)
            r.observed = win.title if win else ""
            r.ok = bool(re.search(p["pattern"], r.observed, re.I))
        elif k == "url":
            r.observed = page_url(session, ctx)
            r.ok = bool(r.observed) and bool(re.search(p["pattern"], r.observed, re.I))
        elif k in ("exists", "absent"):
            res = resolver.resolve(session, ctx, parse(p["target"]))
            exists = res.kind in ("FOUND", "AMBIGUOUS")
            r.observed = len(res.matches) if res.matches else int(res.found)
            snap = res.snapshot
            if (k == "absent" and not exists and snap is not None
                    and (snap.readiness in ("UNTRUSTED", "OPAQUE") or len(snap.nodes) <= 2)):
                # A half-drawn or unreadable tree "lacks" everything. That proves nothing
                # (live: a 1-element WhatsApp tree once passed "the row is gone").
                r.unverifiable = True
                r.detail = f"can't prove it's gone: the tree is {snap.readiness.lower()} ({len(snap.nodes)} elements)"
                return r
            r.ok = exists if k == "exists" else not exists
        elif k == "value":
            node, why = _node_for(session, ctx, p["target"])
            if node is None:
                r.detail = why
                return r
            err, v = raw.attr(node.ref, "AXValue")
            if err == raw.INVALID_UI_ELEMENT:
                session.bindings.get("_ref_cache", {}).pop((ctx.pid, p["target"]), None)
                r.detail = "target went away"
                return r
            have, want, op = _text(v), str(p.get("text") or ""), p["op"]
            r.observed = have
            if op == "equals":
                r.ok = fold(have) == fold(want)
            elif op == "contains":
                r.ok = fold(want) in fold(have)
            elif op == "regex":
                r.ok = bool(re.search(want, have, re.I))
            elif op == "empty":
                r.ok = have == ""
            elif op == "not_empty":
                r.ok = have != ""
        elif k == "state":
            node, why = _node_for(session, ctx, p["target"])
            if node is None:
                r.detail = why
                return r
            state = p["state"]
            attr = {"checked": "AXValue", "selected": "AXSelected", "focused": "AXFocused",
                    "expanded": "AXExpanded", "enabled": "AXEnabled"}[state]
            err, v = raw.attr(node.ref, attr)
            observed = checked_value(v) if state == "checked" else (None if v is None else bool(v))
            if state == "checked" and observed is None and v is None:
                observed = "checked" in node.states if node.states else None
            r.observed = observed
            if observed is None:
                r.unverifiable = True
                r.detail = f"{attr} unreadable"
            else:
                r.ok = bool(observed) == bool(p["is"])
        elif k == "text":
            r = _text_check(session, ctx, check, r)
        elif k == "menu_checked":
            item = menus.find_item(session.menu_items(ctx, refresh=True), p["path"])
            r.observed = None if item is None else item.checked
            r.ok = item is not None and item.checked == bool(p["is"])
            if item is None:
                r.detail = "menu item not found"
    except SelectorError as e:
        r.detail = f"bad selector: {e}"
    except LsfgError as e:
        r.detail = f"{e.kind}: {e.message}"
    return r


def _text_check(session, ctx, check: Check, r: CheckResult) -> CheckResult:
    win = windows.pick_window(ctx.pid)
    if win is None:
        r.unverifiable, r.detail = True, "no window to read"
        return r
    windows.attach_cg(win, ctx.pid)
    if win.cg_id is None or win.bounds is None:
        r.unverifiable, r.detail = True, "window is not on screen (activate first)"
        return r
    region = None
    where = str(check.params.get("region") or "window")
    if where != "window":
        node, why = _node_for(session, ctx, where)
        if node is not None and node.bounds is not None:
            region = raw.bounds_of(node.ref) or node.bounds
    boxes = session.ocr.read(win.cg_id, win.bounds, region)
    r.observed = f"{len(boxes)} text boxes"
    from ..vision.ocr import contains
    r.ok = contains(boxes, str(check.params.get("text") or ""))
    return r


def evaluate_all(checks: list[Check], session) -> tuple[bool, list[CheckResult]]:
    results: list[CheckResult] = []
    all_ok = True
    for _, members in sorted(groups(checks).items()):
        group_ok = False
        for c in members:
            res = evaluate(c, session)
            results.append(res)
            if res.ok:
                group_ok = True
                break                                   # OR within a group
        if not group_ok:
            all_ok = False
    return all_ok, results


def wait_checks(checks: list[Check], session, timeout: float) -> tuple[bool, list[CheckResult], int]:
    """Poll until every group passes: 16 ms growing ×1.5 to 100 ms (150 ms with OCR)."""
    if not checks:
        return True, [], 0
    cap = 0.15 if any(c.kind == "text" for c in checks) else 0.1
    deadline = time.monotonic() + timeout
    delay, polls = 0.016, 0
    while True:
        session.check()
        ok, results = evaluate_all(checks, session)
        polls += 1
        if ok or time.monotonic() >= deadline:
            return ok, results, polls
        time.sleep(delay)
        delay = min(cap, delay * 1.5)
