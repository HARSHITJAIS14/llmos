#!/usr/bin/env python3
"""PostToolUse: enforce declared postconditions after agent-desktop actions.

Protocol (taught by the atree skill): BEFORE any state-mutating action, the
model writes its postcondition to .atree/state/pending_postcondition.json.
After the action runs, this hook evaluates it against a fresh capture:

  pass -> outcome recorded (registry hit + ledger evidence), file consumed
  fail -> exit 2: the failure is fed back to the model as a blocking error,
          with the free vision rungs suggested before any retry

No pending postcondition on a mutating action -> a nag, not a block.
"""
import json
import sys
import time

from _common import (ACTION_COMMANDS, PENDING_PC, append_outcome, bash_command,
                     block, emit_context, is_agent_desktop, read_event)

event = read_event()
cmd = bash_command(event)
if not is_agent_desktop(cmd) or not ACTION_COMMANDS.search(cmd):
    sys.exit(0)

if not PENDING_PC.exists():
    emit_context(
        "[atree] Mutating action ran with NO declared postcondition. Every "
        "action needs one — write it to .atree/state/pending_postcondition.json "
        "BEFORE acting (see the atree skill, 'declare-then-act')."
    )

from core import postconditions as pc_mod  # noqa: E402

try:
    pc = pc_mod.Postcondition.from_json(PENDING_PC.read_text())
except Exception as exc:
    PENDING_PC.unlink(missing_ok=True)
    block(f"[atree] Postcondition file was malformed ({exc}). Re-declare it and re-verify the last action manually.")

verdict = pc_mod.evaluate_live(pc)
PENDING_PC.unlink(missing_ok=True)

record = {
    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "action": cmd[:300],
    "app": pc.app,
    "postcondition": {"kind": pc.kind, "expect": pc.expect, "description": pc.description},
    "verdict": "pass" if verdict.ok else "fail",
    "detail": verdict.detail,
}
append_outcome(record)

if verdict.ok:
    emit_context(
        f"[atree] VERIFIED: {pc.description or pc.kind} — {verdict.detail}"
        + (f" (at {verdict.matched_path})" if verdict.matched_path else "")
    )

block(
    f"[atree] POSTCONDITION FAILED: {pc.description or pc.kind}\n"
    f"  expected: {json.dumps(pc.expect)}\n"
    f"  observed: {verdict.detail}\n"
    "The action did not achieve its intended state change. Do NOT retry the "
    "same action blindly. Diagnose first, in order:\n"
    "  1. re-capture scoped state (the diff hook will show what actually changed)\n"
    "  2. free vision rungs: python3 -m core.vision '<bounds-json>' '<expected text>'\n"
    "  3. only if still inconclusive, Read the cropped screenshot it produces\n"
    "If this element came from a registry recall, treat the entry as stale."
)
