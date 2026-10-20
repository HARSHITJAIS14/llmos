---
description: Batched review — promote corroborated learning candidates into archetype references
---

Run the batched learning review per the `atree-learn` skill:

1. `python3 -m core.ledger review` from the plugin root.
2. For each PROMOTABLE candidate: decide archetype vs app-specific, write into
   the correct `skills/atree/references/*.md` with a provenance comment,
   respecting the ~40-line budget (supersede, don't append past it).
3. For each held candidate, state what evidence is missing (second independent
   run? repro?) — do not promote it anyway.
4. Merge duplicate candidates before writing.
5. Report a table: promoted / held / merged / refuted, with reasons.
