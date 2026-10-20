"""Shared plumbing for atree hooks. Hooks must be FAST and must no-op quickly
on anything that is not an agent-desktop invocation."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(PLUGIN_ROOT))

# Fixed location, independent of session cwd — the `ax` wrapper, the hooks,
# and any shell the model spawns must all agree without coordination.
STATE_DIR = Path.home() / ".atree" / "state"

LAST_SNAPSHOT = STATE_DIR / "last_snapshot.json"
PENDING_PC = STATE_DIR / "pending_postcondition.json"
OUTCOMES = STATE_DIR / "outcomes.jsonl"

ACTION_COMMANDS = re.compile(
    r"\b(click|double-click|right-click|type|set-value|clear|focus|select|toggle|"
    r"check|uncheck|expand|collapse|scroll|scroll-to|press|mouse-click|batch)\b"
)


def read_event() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def bash_command(event: dict) -> str:
    if event.get("tool_name") != "Bash":
        return ""
    return (event.get("tool_input") or {}).get("command", "") or ""


def is_agent_desktop(cmd: str) -> bool:
    return "agent-desktop" in cmd


def snapshot_output_path(cmd: str) -> str | None:
    """If the command redirected a snapshot to a file, find that file."""
    if "snapshot" not in cmd:
        return None
    m = re.search(r">\s*([^\s;|&]+\.json)", cmd)
    return m.group(1) if m else None


def emit_context(text: str) -> None:
    """PostToolUse: feed text back into the model's context, exit 0."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": text,
        }
    }))
    sys.exit(0)


def block(message: str) -> None:
    """PostToolUse: exit 2 — stderr is fed to the model as a blocking error."""
    print(message, file=sys.stderr)
    sys.exit(2)


def append_outcome(record: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with OUTCOMES.open("a") as f:
        f.write(json.dumps(record) + "\n")
