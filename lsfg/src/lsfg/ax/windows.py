"""Windows: the AX candidate set is the truth; CG windows only give capture ids (§6.6).

Measured on this machine: windows on another Space were missing from AXWindows and from the
app's AXChildren, but AXFocusedWindow/AXMainWindow still returned them; Safari full screen
reports subrole AXDialog; Safari listed a 33 px-tall layer-0 strip before its real window.
"""
from __future__ import annotations

from typing import Any

import Quartz

from ..types import WindowInfo
from . import raw
from .normalize import norm, truthy

WIN_ATTRS = ["AXRole", "AXSubrole", "AXTitle", "AXPosition", "AXSize", "AXMinimized", "AXModal",
             "AXMain", "AXFocused", "AXFullScreen", "AXSheets"]
WINDOW_ROLES = ("AXWindow", "AXSheet", "AXDialog")
TRANSIENT_ROLES = ("AXMenu", "AXPopover", "AXSheet", "AXDialog")
HELPER_SIZES = {(0, 0), (1, 1), (64, 64), (500, 500)}


def _dedupe(refs: list[Any]) -> list[Any]:
    out: list[Any] = []
    for r in refs:
        if raw.is_ref(r) and not any(raw.cf_equal(r, o) for o in out):
            out.append(r)
    return out


def window_candidates(pid: int) -> list[WindowInfo]:
    """Union of AXWindows, window-role AXChildren, AXFocusedWindow, AXMainWindow (never AXWindows alone)."""
    app = raw.app_element(pid)
    err, a = raw.batch(app, ["AXWindows", "AXFocusedWindow", "AXMainWindow", "AXChildren"])
    focused, main = a.get("AXFocusedWindow"), a.get("AXMainWindow")
    refs = _dedupe(list(a.get("AXWindows") or []) + list(a.get("AXChildren") or []) + [focused, main])
    out: list[WindowInfo] = []
    for ref in refs:
        err, w = raw.batch(ref, WIN_ATTRS)
        if err != raw.OK or w.get("AXRole") not in WINDOW_ROLES:
            continue
        pos, size = w.get("AXPosition"), w.get("AXSize")
        out.append(WindowInfo(
            ref=ref, title=norm(w.get("AXTitle") if isinstance(w.get("AXTitle"), str) else ""),
            bounds=(pos[0], pos[1], size[0], size[1]) if pos and size else None,
            role=w.get("AXRole", ""), subrole=w.get("AXSubrole") if isinstance(w.get("AXSubrole"), str) else None,
            minimized=truthy(w.get("AXMinimized")), focused=raw.cf_equal(ref, focused),
            main=raw.cf_equal(ref, main), fullscreen=truthy(w.get("AXFullScreen")),
            modal=truthy(w.get("AXModal")), sheets=[s for s in (w.get("AXSheets") or []) if raw.is_ref(s)],
        ))
    return out


def pick_window(pid: int, hint_title: str | None = None) -> WindowInfo | None:
    wins = [w for w in window_candidates(pid) if not w.minimized]
    if not wins:
        return None
    if hint_title:
        want = norm(hint_title).casefold()
        exact = [w for w in wins if w.title.casefold() == want]
        part = [w for w in wins if want and want in w.title.casefold()]
        if exact or part:
            return (exact or part)[0]
    for w in wins:
        if w.focused:
            return w
    for w in wins:
        if w.main:
            return w
    std = [w for w in wins if w.subrole in ("AXStandardWindow", "AXDialog")]
    return max(std or wins, key=lambda w: w.area)


def minimized_windows(pid: int) -> list[WindowInfo]:
    return [w for w in window_candidates(pid) if w.minimized]


def on_screen_window(pid: int) -> bool:
    """A real (not ghost-strip) window of this app is on screen now."""
    return any(w["bounds"][3] > 40 for w in cg_windows(pid, on_screen=True))


def cg_windows(pid: int | None = None, on_screen: bool = True) -> list[dict]:
    opts = (Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
            if on_screen else Quartz.kCGWindowListOptionAll)
    out: list[dict] = []
    for w in Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or []:
        owner = int(w.get(Quartz.kCGWindowOwnerPID, -1))
        if pid is not None and owner != pid:
            continue
        if int(w.get(Quartz.kCGWindowLayer, 0) or 0) != 0:
            continue
        if float(w.get(Quartz.kCGWindowAlpha, 1.0) or 0.0) <= 0:
            continue
        b = w.get(Quartz.kCGWindowBounds) or {}
        try:
            bounds = (float(b["X"]), float(b["Y"]), float(b["Width"]), float(b["Height"]))
        except (KeyError, TypeError, ValueError):
            continue
        out.append({"id": int(w.get(Quartz.kCGWindowNumber, 0) or 0), "pid": owner, "bounds": bounds,
                    "title": str(w.get(Quartz.kCGWindowName, "") or "")})
    return out


def _same_bounds(a, b) -> bool:
    return a is not None and b is not None and all(abs(x - y) < 0.5 for x, y in zip(a, b))


def is_thumbnail(cg: dict) -> bool:
    return cg["bounds"][2] <= 200 and cg["bounds"][3] <= 200     # Dock proxy (LAW-WIN-4)


def is_ghost_cg(cg: dict, ax_windows: list[WindowInfo]) -> bool:
    w, h = cg["bounds"][2], cg["bounds"][3]
    if (round(w), round(h)) in HELPER_SIZES:                         # LAW-WIN-9
        return True
    matched = any(_same_bounds(cg["bounds"], aw.bounds) for aw in ax_windows)
    if h <= 40 and (w >= 1000 or not matched):                       # LAW-WIN-2 strip (33 px seen live)
        return True
    return False


def attach_cg(win: WindowInfo, pid: int, ax_windows: list[WindowInfo] | None = None) -> None:
    """Find the capture id for an AX window: exact bounds first (LAW-WIN-5), then title."""
    cgs = [c for c in cg_windows(pid) if not is_ghost_cg(c, ax_windows or [win]) and not is_thumbnail(c)]
    for c in cgs:
        if _same_bounds(c["bounds"], win.bounds):
            win.cg_id, win.on_screen = c["id"], True
            return
    for c in cgs:
        if win.title and c["title"] and norm(c["title"]) == win.title:
            win.cg_id, win.on_screen = c["id"], True
            return
    win.cg_id, win.on_screen = None, False


def transient_surfaces(pid: int) -> list[Any]:
    """Open context menus / popovers / sheets hang off the app element."""
    err, a = raw.batch(raw.app_element(pid), ["AXChildren"])
    out = []
    for ref in a.get("AXChildren") or []:
        if not raw.is_ref(ref):
            continue
        e, r = raw.batch(ref, ["AXRole"])
        if r.get("AXRole") in TRANSIENT_ROLES:
            out.append(ref)
    return out


def census_ghost(entry: dict) -> bool:
    """LAW-WIN-1 exactly as mined, for agent-desktop list-windows entries (fixtures/tests)."""
    b = entry.get("bounds") or {}
    w, h = float(b.get("width", 0) or 0), float(b.get("height", 0) or 0)
    if entry.get("visible") or entry.get("is_focused"):
        return False
    if (entry.get("title") or "") != (entry.get("app_name") or ""):
        return False
    return (h <= 30 and w >= 1000) or (round(w), round(h)) in HELPER_SIZES
