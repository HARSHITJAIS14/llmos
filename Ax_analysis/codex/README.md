# atree codex — status: lean run complete (2026-09-30)

The knowledge layer mined from the AX census. The lean run finished: 6 of 8 topics mined, schema, 24 per-app files, and the playbook are written. Not done: geometry and fingerprint topics, and the adversarial check.

## What exists

| File | What it is | Status |
|---|---|---|
| `laws.md` | **71 laws** (59 mined + 12 lifecycle) with evidence, exceptions, rules, in 6 topics + a ranked top-10 | 6 of 8 topics, unverified |
| `mined_laws.json` | The first 59 laws as structured data (`{dimension: [{law, evidence, exceptions, deterministic_rule, confidence}]}`) | complete |
| `lifecycle_laws.json` | The 12 lifecycle laws (LAW-LIFE-1..12) in the same shape | complete |
| `all_findings.txt` | Flat dump of the first 59 findings | complete (no lifecycle) |
| `schema.json` + `schema.md` | Formal per-app knowledge format (16 top-level fields, closed quirk list) | complete |
| `apps/<app>.json` | 24 per-app files following the schema (all parse; strict schema check not run, no jsonschema lib) | complete |
| `playbook.md` | 7 procedures with no model in the loop: READY, PICK-WINDOW, FIND, ACT, VERIFY, CLASSIFY, ESCALATE | complete |

Upstream inputs remain in `Ax_analysis/`: 24 app directories (each with `meta.json`, `windows.json`, `skeleton.json`, `full.json`, `forced.json`, `analysis.md`), the census `README.md`, and the capture scripts.

## Phase status

| Phase | Deliverable | Status |
|---|---|---|
| 1. Mine | 8 topic miners | **6 of 8 done**. Missing: geometry, fingerprint |
| 2. Verify | Adversarial counterexample hunts | **not run** |
| 3. Codify | `schema.json` + `schema.md` | done |
| 4. Extract | `apps/<app>.json` x 24 | done |
| 5. Synthesize | `playbook.md` | done (no `GAPS.md`) |

## The six topics that landed

- **WIN — windows & ghosts (10 laws).** 80.7% of window-server entries are phantoms; the ghost predicate, the thumbnail-proxy trap, and a best-window algorithm measured at 100% on the 15 winnable apps.
- **ACT — roles & actions (13 laws).** A closed 49-role vocabulary with no `tab`/`menuitem`/`listitem`; Toggle as an exact biconditional; per-framework Click/RightClick trustworthiness; the AppKit textfield-is-a-label trap.
- **ID — identity & selectors (12 laws).** native_id stability tiers; React auto-ids; "identity lives in value"; (role,name) is only 68% unique; ref_id is strictly snapshot-scoped; the complete resolver fallback chain.
- **TXT — text & values (12 laws).** Key-absence as the empty signal; where readable text lives per framework; the write-only-surface detector; toggle state as '0'/'1'; a whole document as one giant value.
- **LIFE — lifecycle (12 laws).** The husk is the depth cap, not a cold renderer; a 10/10 untrusted-capture predicate; native trees are ready in the background; Telegram is opaque from capture 1; a readiness ladder that sorts all 24 apps in at most 2 snapshots.
- **STR — structure & depth (12 laws).** Root-to-webarea path as a framework fingerprint; native ≤ depth 9 vs web ≥ depth 16; **silent depth-cap truncation**; truncation-marker semantics; noise ratio stratification.

## How to use this now

`laws.md` is directly implementable. The rules are written as pseudocode against the node shape agent-desktop emits, so the selector resolver, window picker, and capture-budget logic can be built from it today — that was the point of the exercise. Start with the ranked top-10 at the bottom of `laws.md`; those ten change what you build, the rest refine it.

## Caveats that matter

1. **Unverified.** Every law is one analyst's computation. The verify phase existed specifically to hunt counterexamples in apps the evidence didn't cite, and it never ran. Confidence labels are self-assessed.
2. **Single-surface bias.** Most apps were captured once, often on a splash/login/idle screen (Keynote = "What's New" splash, Claude = sign-in, Safari = native Start Page with no webarea). Laws about those apps describe that surface.
3. **One known-bad input.** `music/forced.json` actually captured YT Music (LAW-STR-12). Any per-app stat citing Music's forced data is suspect.
4. **Two blind spots.** Nothing here systematically covers coordinate/bounds trust (geometry) or a tested framework classifier (fingerprint) — though LAW-STR-1, LAW-STR-5, and LAW-ACT-13 give partial fingerprint coverage.

## What's left

- **fingerprint** topic (a tested framework classifier). `playbook.md` CLASSIFY is a first version built from LAW-LIFE-3, LAW-STR-1, and LAW-ID-1.
- **geometry** topic (when bounds can be trusted).
- **Adversarial check** of all 71 laws.

Cost so far: first run ~1.6M tokens (stopped), lean run 1.26M tokens.

## Correction worth knowing

LAW-LIFE-1 overturns the census README's "handshake" story: the Electron husk was the depth-10 cap, not a missing `AXManualAccessibility` handshake. The depth-10 tree is an exact prefix of the depth-40 tree. Fix = capture deeper, not activate or wait.
