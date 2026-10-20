#!/usr/bin/env python3
"""SessionStart: load ONLY the archetype index plus a one-line registry
summary. Everything else is progressive disclosure — this hook is the whole
always-on token budget."""
import sys
from pathlib import Path

from _common import PLUGIN_ROOT

index = PLUGIN_ROOT / "skills" / "atree" / "references" / "archetypes.md"
lines = []
if index.exists():
    lines.append(index.read_text().strip())

try:
    from core import registry
    if registry.DB_PATH.exists():
        con = registry.connect()
        rows = con.execute(
            "SELECT name, archetype FROM apps ORDER BY last_seen DESC LIMIT 8"
        ).fetchall()
        if rows:
            known = ", ".join(f"{r['name']} ({r['archetype'] or '?'})" for r in rows)
            lines.append(
                f"\n[atree registry] Known apps: {known}. Before ANY desktop task, "
                "run the pre-flight: python3 -m core.recall \"<task>\" \"<App>\""
            )
except Exception:
    pass

if lines:
    print("\n".join(lines))
sys.exit(0)
