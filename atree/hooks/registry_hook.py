#!/usr/bin/env python3
"""PostToolUse: deposit what every snapshot revealed into the app registry.

Runs after state_diff_hook on the same captures. Deposits are bounded to
named interactive elements; content-region names are sanitized by
core.registry (selectors, not content); denylisted apps take no deposits.
Silent — deposits never touch the model's context.
"""
import json
import re
import sys
from pathlib import Path

from _common import bash_command, is_agent_desktop, read_event, snapshot_output_path

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

m = re.search(r"--app\s+(?:\"([^\"]+)\"|'([^']+)'|(\S+))", cmd)
app_name = next((g for g in (m.groups() if m else ()) if g), None)
if not app_name:
    sys.exit(0)

from core import axdiff, registry  # noqa: E402

if registry.denied(app_name):
    sys.exit(0)

try:
    tree = json.loads(snap_file.read_text())
except (json.JSONDecodeError, OSError):
    sys.exit(0)

INTERACTIVE = {"button", "textfield", "textarea", "searchfield", "combobox",
               "checkbox", "menuitem", "tab", "link", "slider", "popupbutton"}
# Path segments that indicate user content rather than UI chrome.
CONTENT_HINT = re.compile(r"/(webarea|list|table|outline|row|cell)\b", re.IGNORECASE)

content, _ = axdiff.flatten(tree)
con = registry.connect()
app_id = registry.get_or_create_app(con, app_name)
if app_id is None:
    sys.exit(0)

deposited = 0
for path, attrs in content.items():
    role = attrs.get("role", "")
    name = str(attrs.get("name", ""))
    if role not in INTERACTIVE or not name or deposited >= 200:
        continue
    registry.upsert_element(
        con, app_id, identity_path=path, role=role, name=name,
        is_content=bool(CONTENT_HINT.search(path)),
    )
    deposited += 1

sys.exit(0)
