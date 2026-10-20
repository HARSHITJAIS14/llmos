---
description: Query what atree already knows about an app or task (registry pre-flight)
argument-hint: <task or app name>
---

Query the registry for: $ARGUMENTS

1. If $ARGUMENTS names an app: `python3 -m core.registry app "<App>"` — report
   the profile (archetype, element count, route count, last seen).
2. If it describes a task: `python3 -m core.recall "<task>" "<App if known>"`
   — report the recall level and what it enables (L1 replay / L2 known
   elements / L3 informed discovery / cold miss).
3. This is also the privacy inspection surface: on request, show stored
   element rows verbatim so the user can see exactly what is held, and note
   that `python3 -m core.registry forget "<App>"` erases an app completely.
