"""Pointer clicks with cursor restore and a hit-test gate (implementation.md §9.3).

The gate asks AX what is under the click point (0.2 ms). If it isn't the target or within
three parents of it, something covers the target and we refuse instead of clicking blind.
"""
from __future__ import annotations

import time
from typing import Any

import Quartz

from ..errors import ActionFailed
from ..ax import raw
from . import focus

_SOURCE = None


def _source():
    global _SOURCE
    if _SOURCE is None:
        _SOURCE = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStatePrivate)
    return _SOURCE


def _parents(ref: Any, n: int) -> list[Any]:
    out = []
    cur = ref
    for _ in range(n):
        err, p = raw.attr(cur, "AXParent")
        if not raw.is_ref(p):
            break
        out.append(p)
        cur = p
    return out


def hit_test_ok(pid: int, x: float, y: float, target_ref: Any) -> bool:
    err, hit = raw.hit_test(raw.app_element(pid), x, y)
    if not raw.is_ref(hit):
        return False
    if raw.cf_equal(hit, target_ref):
        return True
    if any(raw.cf_equal(p, target_ref) for p in _parents(hit, 3)):      # hit is inside the target
        return True
    return any(raw.cf_equal(p, hit) for p in _parents(target_ref, 3))   # target is inside the hit


def _post_mouse(kind, x: float, y: float, button, click_state: int = 1) -> None:
    ev = Quartz.CGEventCreateMouseEvent(_source(), kind, (x, y), button)
    Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, click_state)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def click_at(x: float, y: float, *, button: str = "left", count: int = 1) -> None:
    """Warp, click, and put the cursor back (in-process version of atree's stealth_click)."""
    if button == "right":
        btn, down, up = Quartz.kCGMouseButtonRight, Quartz.kCGEventRightMouseDown, Quartz.kCGEventRightMouseUp
    else:
        btn, down, up = Quartz.kCGMouseButtonLeft, Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp
    saved = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
    Quartz.CGWarpMouseCursorPosition((x, y))
    _post_mouse(Quartz.kCGEventMouseMoved, x, y, Quartz.kCGMouseButtonLeft)
    for i in range(count):
        _post_mouse(down, x, y, btn, i + 1)
        _post_mouse(up, x, y, btn, i + 1)
        if i + 1 < count:
            time.sleep(0.03)
    time.sleep(0.01)
    Quartz.CGWarpMouseCursorPosition((saved.x, saved.y))


def click_node(node, pid: int, *, button: str = "left", count: int = 1, window_ref: Any = None,
               require_hit: bool = True) -> None:
    if node.bounds is None or node.zero_area:
        raise ActionFailed("target has no usable bounds for a pointer click")
    if "offscreen" in node.states:
        raise ActionFailed("target is offscreen; scroll it into view first")
    if not focus.activate(pid, window_ref):
        raise ActionFailed("could not bring the app to the front for a pointer click")
    fresh = raw.bounds_of(node.ref) if node.ref is not None else None   # bounds belong to THIS moment
    x, y, w, h = fresh or node.bounds
    cx, cy = x + w / 2.0, y + h / 2.0
    if require_hit and node.ref is not None and not hit_test_ok(pid, cx, cy, node.ref):
        raise ActionFailed("something covers the target (hit-test mismatch)")
    focus.guard(pid)
    click_at(cx, cy, button=button, count=count)


def scroll_at(x: float, y: float, dy: int = 0, dx: int = 0) -> None:
    saved = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
    Quartz.CGWarpMouseCursorPosition((x, y))
    ev = Quartz.CGEventCreateScrollWheelEvent(_source(), Quartz.kCGScrollEventUnitPixel, 2, int(dy), int(dx))
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    time.sleep(0.01)
    Quartz.CGWarpMouseCursorPosition((saved.x, saved.y))
