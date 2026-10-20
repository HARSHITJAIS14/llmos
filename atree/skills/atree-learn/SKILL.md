---
name: atree-learn
description: >
  Promotion rules for atree knowledge: candidate learnings -> confirmed
  archetype references, and discovered routes -> compiled route commands.
  Use when running /ax-learn, when asked to "promote", "confirm", or
  "consolidate" learnings, or when a discovery session produced a working
  route worth compiling.
---

# atree-learn: evidence-gated promotion

Learnings grow only on evidence and shrink on contradiction. You never
author a learning from memory of a session — you promote what the ledger
supports.

## Promoting a learning (candidate -> confirmed)

1. `python3 -m core.ledger review` — only rows marked PROMOTABLE are eligible.
   The gate (>=2 independent observations + a repro) is mechanical; do not
   argue past it, and do not promote a held candidate "because it is obviously
   true". If it is obviously true, a second independent run is cheap.
2. For each promotable candidate, judge GENERALIZATION only: does this belong
   to the archetype (goes in the archetype reference) or to one app (belongs
   in the registry, not in context)?
3. Write it into the correct `skills/atree/references/<archetype>.md` with a
   provenance comment: `<!-- provenance: <date>, <apps>, agent-desktop <ver> -->`.
4. **Budget: ~40 lines per reference file.** Over budget → the new entry must
   supersede or merge into an existing one. Growth is replacement, not
   accumulation. Move superseded text's candidate file to `learnings/archive/`.
5. Duplicates across candidates: merge before writing, keep the union of
   evidence.

## Compiling a route (discovery -> commands/route-*.md)

A discovered sequence that succeeded end-to-end twice becomes a route command:

1. Write `commands/route-<app>-<verb>.md` (top level — subdirectories under
   commands/ do not register): frontmatter description +
   argument-hint, then the exact step sequence — every step with its
   postcondition declaration, every wait as a predicate (`wait --element`,
   `wait --text`), zero fixed sleeps.
2. Save the machine-readable form too:
   `python3 -c "...registry.save_route(...)"` so recall returns L1.
3. A route that fails on replay falls back to discovery per the atree skill;
   if the rediscovered route differs, update BOTH the command file and the
   registry, and note the old form in the route file's history comment.

## Demotion

`core.ledger.record_failure(<id>)` on any confirmed learning whose strategy
fails verification. Two failures auto-refute: remove the corresponding lines
from the reference file in the same pass — a refuted rule left in context is
worse than no rule.
