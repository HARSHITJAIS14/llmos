---
description: Discover a route for a new desktop task via the atree cognitive loop
argument-hint: <task description, e.g. "mute Slack notifications for 1 hour">
---

Run the atree discovery loop for: $ARGUMENTS

1. Pre-flight: `python3 -m core.recall "$ARGUMENTS" "<App>"` from the plugin
   root. If it returns L1, replay instead of discovering. L2: start from the
   known elements.
2. Follow the `atree` skill exactly: classify archetype -> load ONE reference
   -> skeleton-first perceive (snapshot redirected to
   `.atree/state/current_snapshot.json`) -> declare postcondition -> act ->
   hook verifies. One atomic action per step; the state diff tells you whether
   it landed.
3. Ambiguous target (multiple matching contacts/files/buttons): stop and ask.
4. On completion, report: the step sequence that worked, per-step
   postconditions, turn count, and which reach strategies worked where.
5. If the full sequence succeeded end-to-end, offer to compile it into a
   route per the `atree-learn` skill (do not compile a first-run route
   without asking — twice-run is the compile gate).
