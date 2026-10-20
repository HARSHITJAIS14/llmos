#!/usr/bin/env python3
"""Single PostToolUse dispatcher — one lightweight process instead of three.

The common case (a Bash call that has nothing to do with agent-desktop) exits
in ~40ms before importing anything heavy. Only matching events pay for the
real hooks, which run in-process via runpy.
"""
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

raw = sys.stdin.read()
try:
    event = json.loads(raw)
except (json.JSONDecodeError, ValueError):
    sys.exit(0)
if event.get("tool_name") != "Bash":
    sys.exit(0)
cmd = (event.get("tool_input") or {}).get("command", "") or ""
if "agent-desktop" not in cmd:
    sys.exit(0)

is_snapshot = "snapshot" in cmd and re.search(r">\s*\S+\.json", cmd)
is_action = re.search(
    r"\b(click|double-click|right-click|type|set-value|clear|focus|select|toggle|"
    r"check|uncheck|expand|collapse|scroll|scroll-to|press|mouse-click|batch)\b", cmd)
if not (is_snapshot or is_action):
    sys.exit(0)

sys.path.insert(0, str(HERE))


def run(script: str) -> int:
    """Run a hook script in-process, re-feeding it the event on stdin."""
    import runpy
    sys.stdin = io.StringIO(raw)
    try:
        runpy.run_path(str(HERE / script), run_name="__main__")
        return 0
    except SystemExit as e:
        return int(e.code or 0)
    except Exception:
        return 0  # a broken hook must never block the session


if is_snapshot:
    run("state_diff_hook.py")   # prints its context JSON itself
    run("registry_hook.py")     # silent deposits
    sys.exit(0)
sys.exit(run("verify_hook.py"))  # exit 2 propagates = blocking failure
