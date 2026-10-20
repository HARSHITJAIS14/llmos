# First training inventory

Offline inspection of `contextual_lite_runs/full_daily_run`, 2026-10-18. No annotation API calls or GPU training jobs were started.

Verified 190 annotation files, original source hashes, report-image pixel equivalence, schema, in-bounds geometry, hierarchy and proposal correspondence. Report PNGs were re-encoded by the annotation runner, so file hashes differ from original captures; decoded image pixels match. No inspection failures.

- 10,434 nodes: 190 roots, 1,453 regions, 8,791 elements.
- 9,405 proposal dispositions: 8,070 retained, 241 rejected, 1,094 unresolved.
- 163 distinct decoded images, with 17 duplicate groups comprising 27 redundant captures beyond their representatives. Exact duplicates are not the only leakage risk; related states from one session also need grouping.
- 9,523 non-root nodes are candidates after excluding nodes linked to unresolved/rejected proposals. This is a structural eligibility count, not a semantic accuracy score.
- Zero records are marked human-reviewed and no nodes have literal visible_text supervision.

## Files

`inventory.json` contains counts, application distribution and exact duplicate groups. `screens.jsonl` lists verified image/annotation paths and metadata without assigning splits. `candidate_masks.jsonl` records node eligibility hints: uncertain proposal associations are excluded and selected-state labels require review. These are inventory artifacts, not accepted training targets.

## Next training experiment

Use this as the first teacher-labeled development set. Preserve descriptions and contextual prose at region and element levels; do not reduce the task to icon classification.

Before training, preserve raw teacher roles and correct or mask lossy aliases. The runner currently maps slider to toggle and radio to checkbox; these are different control types. A synonym such as treeitem to list_item may be reasonable, but its original label should remain available. Do not relabel all checkboxes/toggles blindly: identify affected records from raw responses.

Group exact duplicate captures and related sessions before selecting train/validation data. Independently review a small held-out set across apps for context, states and region coverage. Do not report teacher agreement on unreviewed labels as ground-truth accuracy. Blank/loading captures are legitimate states but should not dominate content learning.

Train a pretrained visual encoder with a compact context module using the region and element descriptions as semantic supervision. Measure role/context/relationship quality and inference latency separately. Plan structured outputs first; arbitrary prose generation and exact-text recognition require explicit modeling and evaluation.

The completed screen IDs are interleaved, not simply 0001–0190. Resume from the manifest/output state. Do not assume the remaining work begins at 0191. Quota reset time and account-wide remaining allowance must be checked against the actual provider configuration before resuming; this inventory makes no claim about them.
