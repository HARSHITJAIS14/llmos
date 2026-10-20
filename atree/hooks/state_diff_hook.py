#!/usr/bin/env python3
"""PostToolUse: replace snapshots with diffs in the model's context.

Convention (taught by the atree skill): snapshot output is always redirected
to a file — `agent-desktop snapshot ... > .atree/state/current_snapshot.json`
— so the raw tree never lands in context. This hook diffs the new capture
against the previous one and injects only the compact identity-keyed diff.

The sidecar (path -> ref_id/bounds) is written next to the state file for the
executor to resolve against; it is never injected.
"""
import json
import sys
import time
from pathlib import Path

from _common import (LAST_SNAPSHOT, STATE_DIR, bash_command, emit_context,
                     is_agent_desktop, read_event, snapshot_output_path)

MAX_DIFF_CHARS = 12000  # a diff bigger than this means capture was too broad

event = read_event()
cmd = bash_command(event)
if not is_agent_desktop(cmd):
    sys.exit(0)
out_path = snapshot_output_path(cmd)
if not out_path:
    sys.exit(0)

snap_file = Path(out_path)
if not snap_file.is_absolute():
    snap_file = Path(event.get("cwd", ".")) / snap_file
if not snap_file.exists():
    sys.exit(0)

from core import axdiff  # noqa: E402  (after _common set sys.path)

try:
    curr = json.loads(snap_file.read_text())
except (json.JSONDecodeError, OSError):
    sys.exit(0)

# Never baseline a failed capture — surface the error usefully instead.
if isinstance(curr, dict) and curr.get("ok") is False:
    err = curr.get("error") or {}
    emit_context(
        "[atree] Snapshot FAILED (%s): %s\nSuggestion: %s" % (
            err.get("code", "?"), err.get("message", ""), err.get("suggestion", ""))
    )

STATE_DIR.mkdir(parents=True, exist_ok=True)

if not LAST_SNAPSHOT.exists():
    content, sidecar = axdiff.flatten(curr)
    LAST_SNAPSHOT.write_text(json.dumps(curr))
    (STATE_DIR / "sidecar.json").write_text(json.dumps(sidecar))
    interesting = [
        f"  {p} => {json.dumps(a, ensure_ascii=False)}"
        for p, a in sorted(content.items())
        if a.get("role") in ("button", "textfield", "textarea", "combobox", "checkbox",
                             "menuitem", "tab", "link", "sheet", "window", "searchfield")
    ][:80]
    emit_context(
        "[atree] Baseline captured (%d nodes). Interactive elements:\n%s\n"
        "(Full tree saved at %s — do not cat it; refs/bounds resolve via "
        ".atree/state/sidecar.json)" % (len(content), "\n".join(interesting), snap_file)
    )

try:
    prev = json.loads(LAST_SNAPSHOT.read_text())
except (json.JSONDecodeError, OSError):
    prev = {}

result = axdiff.diff(prev, curr, from_label=f"S_t-1", to_label=f"S_t")
LAST_SNAPSHOT.write_text(json.dumps(curr))
(STATE_DIR / "sidecar.json").write_text(json.dumps(result.sidecar))

ts = time.strftime("%H:%M:%S")
if result.is_empty:
    emit_context(f"[atree {ts}] State diff: NO CHANGE since previous capture. "
                 "If an action preceded this, it was likely swallowed — see the "
                 "vision ladder (rung 2) before retrying blindly.")

text = result.text
if len(text) > MAX_DIFF_CHARS:
    text = text[:MAX_DIFF_CHARS] + f"\n... (truncated; {result.changed} changed lines total — capture was too broad, scope the next snapshot)"

emit_context(
    f"[atree {ts}] State diff (+{result.added}/-{result.removed} lines, "
    f"~{result.tokens} tok vs full snapshot):\n{text}"
)
