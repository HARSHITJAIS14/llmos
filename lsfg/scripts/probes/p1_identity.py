"""E1: is element identity stable across two walks? Compares repr(ref) vs CFHash/CFEqual.
Result on 2026-09-30 (Safari): repr 1/8, CFHash 8/8, CFEqual 8/8.
Usage: python p1_identity.py [AppName ...]   (default: every running regular app)"""
import sys

import ApplicationServices as AS
from CoreFoundation import CFEqual, CFHash

from _common import pid_of, regular_apps


def kids(ref):
    err, v = AS.AXUIElementCopyAttributeValue(ref, "AXChildren", None)
    return list(v) if err == 0 and v else []


def walk(ref, depth, out, maxd=6, cap=400):
    if len(out) >= cap:
        return
    out.append(ref)
    if depth < maxd:
        for c in kids(ref):
            walk(c, depth + 1, out, maxd, cap)


names = sys.argv[1:] or [n for n, _ in regular_apps()]
for name in names:
    pid = pid_of(name)
    if not pid:
        continue
    app = AS.AXUIElementCreateApplication(pid)
    AS.AXUIElementSetMessagingTimeout(app, 1.0)
    err, win = AS.AXUIElementCopyAttributeValue(app, "AXFocusedWindow", None)
    root = win if err == 0 and win is not None else app
    a, b = [], []
    walk(root, 0, a)
    walk(root, 0, b)
    n = min(len(a), len(b))
    same_repr = sum(1 for x, y in zip(a, b) if repr(x) == repr(y))
    same_hash = sum(1 for x, y in zip(a, b) if CFHash(x) == CFHash(y))
    same_eq = sum(1 for x, y in zip(a, b) if CFEqual(x, y))
    distinct = len({CFHash(x) for x in a})
    print(f"{name[:20]:20} nodes={n:4}  repr={same_repr}/{n}  CFHash={same_hash}/{n}  "
          f"CFEqual={same_eq}/{n}  distinct_hash_in_walk={distinct}/{len(a)}")
