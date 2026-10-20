---
description: Skeleton-first accessibility inspection of a running app
argument-hint: <app name, e.g. "Notion">
---

Inspect the accessibility surface of: $ARGUMENTS

1. `agent-desktop snapshot --skeleton --app "$ARGUMENTS" -i --compact > .atree/state/current_snapshot.json`
   (the diff hook will surface the interactive elements; do NOT cat the file).
2. From the skeleton, report: archetype classification (per
   `references/archetypes.md`), window inventory, the main interactive
   regions with their `children_count`s, and any truncated regions that would
   need drill-down.
3. Drill into a region only if the user asks about something inside it.
4. If the app is denylisted (Messages, password managers), refuse and say why.
