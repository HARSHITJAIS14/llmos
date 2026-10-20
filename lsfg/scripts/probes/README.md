# M0 probes

Read-only measurement scripts. The numbers in `../../reasoning.md` §1.1 came from these.
They print counts and timings only, never UI text. `p4` makes network calls to TypeSafe with
synthetic data only.

Run with any Python that has PyObjC (until the lsfg venv exists, use arc-cua's):

```sh
PY=/Users/harshit/Desktop/YC/arc-cua/.venv/bin/python
cd /Users/harshit/Desktop/YC/lsfg/scripts/probes
$PY p1_identity.py Safari Finder          # E1: CFHash vs repr identity
$PY p2_ax_menu_walk_hittest.py            # menus, depth-10 walks, hit-test
$PY p3_capture_ocr.py Safari              # CG list ghosts, capture, OCR
$PY p4_jev_latency.py                     # JEV latency (needs TYPESAFE_API_KEY)
$PY p5_arc_settle.py                      # arc-cua settle bug
```

The host app (Terminal, VS Code, …) needs Accessibility and Screen Recording permission.

Still to write for M0 (see implementation.md §21): E2 background AXPress, E3 AXFrontmost activation,
E4 AXValue on native search fields, E5 cold Electron + AXManualAccessibility, E6 Opus plan latency,
E7 JEV accuracy on real tables, E8 clipboard restore, E9 hit-test agreement, E10 AXURL, E11 AXObserver,
E12 keyboard layout.
