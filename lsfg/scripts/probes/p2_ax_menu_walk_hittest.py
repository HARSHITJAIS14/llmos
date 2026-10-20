"""Menu bar read cost, depth-10 walk cost with leaves-at-cap (LAW-STR-6), hit-test cost.
Result on 2026-09-30: menus 0.6-1.8 ms; Safari 106 nodes/22 ms; YT Music 437 nodes/274 ms with
250 leaves at the cap; hit-test 0.18 ms.
Usage: python p2_ax_menu_walk_hittest.py [AppName ...]"""
import sys

import ApplicationServices as AS

from _common import batch, pid_of, regular_apps, timed

ATTRS = ["AXRole", "AXSubrole", "AXTitle", "AXDescription", "AXValue", "AXEnabled", "AXFocused",
         "AXSelected", "AXExpanded", "AXIdentifier", "AXDOMIdentifier", "AXPlaceholderValue", "AXChildren"]


def walk(ref, depth, maxd, out):
    a = batch(ref, ATTRS)
    if not a:
        return
    kids = list(a.get("AXChildren") or [])
    out.append((depth, bool(kids)))
    if depth >= maxd:
        return
    for ch in kids:
        walk(ch, depth + 1, maxd, out)


def menubar(app):
    mb = batch(app, ["AXMenuBar"]).get("AXMenuBar")
    if mb is None:
        return (0, 0)
    tops = list(batch(mb, ["AXChildren"]).get("AXChildren") or [])
    items = 0
    for top in tops[1:4]:  # skip the Apple menu; read 3 app menus
        for m in list(batch(top, ["AXChildren"]).get("AXChildren") or []):
            items += len(list(batch(m, ["AXChildren"]).get("AXChildren") or []))
    return (len(tops), items)


names = sys.argv[1:] or [n for n, _ in regular_apps()]
for name in names:
    pid = pid_of(name)
    if not pid:
        continue
    app = AS.AXUIElementCreateApplication(pid)
    AS.AXUIElementSetMessagingTimeout(app, 1.0)
    med, mx, (ntop, nitems) = timed(lambda: menubar(app))
    w = batch(app, ["AXFocusedWindow", "AXWindows"])
    fw = w.get("AXFocusedWindow") or (list(w.get("AXWindows") or [None])[0])
    res = "no window"
    if fw is not None:
        def w10():
            out = []
            walk(fw, 0, 10, out)
            return len(out), sum(1 for d, has_kids in out if d == 10 and has_kids)
        wmed, wmx, (n, at_cap) = timed(w10, n=2)
        res = f"walk d10 {wmed:.0f} ms (max {wmx:.0f}) nodes={n} leaves_at_cap_with_children={at_cap}"
        pos = batch(fw, ["AXPosition", "AXSize"])
        ok, pt = AS.AXValueGetValue(pos["AXPosition"], AS.kAXValueCGPointType, None)
        ok2, sz = AS.AXValueGetValue(pos["AXSize"], AS.kAXValueCGSizeType, None)
        hmed, hmx, _ = timed(lambda: AS.AXUIElementCopyElementAtPosition(
            app, pt.x + sz.width / 2, pt.y + 20, None), n=5)
        res += f" | hit-test {hmed:.2f} ms"
    print(f"{name[:18]:18} menubar {med:.1f} ms (max {mx:.1f}) top={ntop} items(3 menus)={nitems} | {res}")
