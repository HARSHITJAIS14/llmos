# Existing AX research in YC: review before further work

Reviewed 2026-10-19. Read-only research audit; no new desktop actions, API calls or benchmark runs. This covers the main research lineage and selected implementations, not every file or every test in the workspace.

## Scope and research lineage

| Location | Existing work | Status/evidence boundary |
|---|---|---|
| `Ax_analysis/` | 28-app census; 24 app analyses; raw full/deeper captures; window and action observations | Capture-specific evidence. Initial narratives have later corrections. |
| `Ax_analysis/codex/` | 71 mined/lifecycle laws, per-app knowledge schema/files, seven deterministic procedures | README explicitly says adversarial verification was not run; geometry and fingerprint topics are incomplete. |
| `LLM_OS/ATree_tool/` | Earlier Notion DFS, task experiments, parser comparison, keyboard/coordinate approaches | Historical experiments, some rules deliberately superseded by atree. |
| `agent-desktop/` | Native AX backend, batched reads, compact-tree collapse, snapshot refs, scoped reads and stale-target handling | Implementation exists; plans and old corpus refer to different stages/versions. Do not assume old limitations describe today's binary. |
| `atree/` | Skeleton-first capture, scoped drill-down, identity-keyed diffs, ref/bounds sidecar, typed postconditions | Actual Python modules and tests exist. Its AGENTS.md explicitly supersedes full-depth/full-tree defaults from ATree_tool. |
| `atree_v2/theoratically.md` | Warm runtime; plan once, execute and verify locally; fewer model turns | Explicitly plan-only. Historical measured numbers and proposed targets are separate. |
| `arc-cua/` | AX/OCR hybrid runtime, target guards, bounded decisions; detailed perception latency study | Actual implementation plus measured limitations. Current `_stable_id` still hashes `repr(ref)`. |
| `lsfg/` | Later synthesis: normalized AX nodes, session identity, bounded walker, compact digest, typed checks, routes and Jev choices | Actual modules and recorded probes/acceptance examples exist. General reliability is not established by a few acceptance examples. |
| `vlm_testing/click_groq_fast/` | Screenshot grounding followed by snapping to AX geometry | Actual scripts and logs; nearest-node output is not independently verified correctness. |

## What was checked directly in raw JSON

Traversed `full.json` and available `forced.json` for all 24 app directories with an analysis.md, counting serialized nodes/depth/frontiers. Selected results:

| App | Default serialized nodes | Deeper/forced serialized nodes |
|---|---:|---:|
| Notion | 19 | 1,004 |
| Discord | 25 | 507 |
| Claude Desktop | 19 | 36 |
| Chrome | 51 | 69 |
| Firefox | 93 | 288 |
| YT Music | 437 | 975 |
| Notes | 49 | 49 |
| Telegram | 1 | 1 |
| Antigravity IDE | 22 | RefMap exceeds 1MB error |

Several older default captures report `complete=true` while serialized nodes have `children_count > len(children)` at depth ten. Therefore that envelope flag alone did not establish semantic completeness in this corpus. These counts are facts about saved captures, not fresh current-machine measurements.

`music/forced.json` is flagged by the later research as a YT Music capture. Do not interpret its larger tree as evidence of improved native Music coverage. Keynote's nine-node initial view and later 689-node view are different app surfaces, not a controlled capture-format comparison.

## Corrections and disagreements to preserve

1. **Handshake versus depth.** The census summary credits AXManualAccessibility for Electron recovery. The later codex points to depth-limit truncation and notes that agent-desktop may already enable the handshake internally. The forced capture script also changes activation and depth. Raw growth alone cannot isolate the cause. Detect frontiers and capture-budget limits before concluding that a renderer is opaque; test handshake effects separately when necessary.
2. **Full DFS versus scoped observation.** Early ATree_tool recommends avoiding skeleton/compact and expanding whole trees. Later agent-desktop implements ref-rooted progressive traversal; atree explicitly supersedes the older advice. Preserve needed content with scoped expansion, not unconditional full DFS or a shallow skeleton treated as complete.
3. **Stable identity versus ref churn.** atree excludes ephemeral refs/bounds from semantic diffs and keeps a sidecar. lsfg's recorded probes found CFHash/CFEqual stable across 393 nodes over repeated walks, while repr was unstable. These observations support session identity plus revalidation; they do not make native references permanent across relaunches or every UI mutation.
4. **Latency has several bottlenecks.** atree_v2 records about 100 ms observations and multi-second model turns. arc-cua records Finder's repeated AX IPC dominating a much slower walk. lsfg identifies identity instability as a cause of settle loops always timing out. Those are different scopes/implementations, not one universal AX latency.

## Existing compact format

`lsfg/src/lsfg/plan/digest.py` already renders a bounded digest: app/window/readiness header, short element aliases, roles, normalized labels, selected values, placeholders, qualifying identifiers, URL, region/list context, and states. It limits static text and deduplicates some nested nodes.

The useful next question is whether this **existing** digest preserves the evidence needed for our tasks and how incomplete observations are disclosed. Writing another YAML/JSON serializer would not answer that.

The normalization rules matter more than punctuation: text can live in name, value or child nodes; AppKit textfield roles can describe labels rather than editable inputs; role/name may be ambiguous; ghost windows and offscreen zero-area elements can misdirect actions. The corpus laws describe these issues but need current fixtures/live checks rather than universal acceptance.

## Existing hybrid grounding experiment

`vlm_testing/click_groq_fast/benchmark_snap_atree.py` captures a screenshot, requests a visual point, converts coordinates, and chooses the nearest AX box center. It hard-codes a Retina division by two and has no distance rejection in the inspected code.

The logs include a 366.3-pixel nearest match and a 102.6-pixel match to a one-pixel-high full-width element, both printed with a success mark. These are successful nearest-neighbor computations, not verified target matches or successful actions. A candidate implementation needs explicit coordinate transforms, actionable/visible candidates, ambiguity/distance rejection, and post-action verification.

## Revised next step

Reuse and compare existing components rather than start another AX implementation:

- Establish the current binary/runtime versions and which tests/examples genuinely pass.
- Evaluate the existing lsfg digest and atree scoped observation/diff on fresh paired screenshots and AX observations.
- For rich AX surfaces, test compact semantic observations and validated refs; request visual context when useful or when AX omits evidence. For opaque/custom-rendered surfaces, use screenshots/OCR. No unbounded retry or depth expansion.
- Measure target selection, stable-state/no-change detection, stale-target rejection, action verification and end-to-end task completion. Distinguish small-fixture rules from empirically validated general behavior.
- Compare screenshot-only, existing AX-only and hybrid modes on the same tasks. The earlier caption utility test is not evidence against native AX state or action references.

The primary remaining work is validation and integration of this substantial existing research, with selective fixes where the evidence shows a gap. No new model training is required for that experiment.

## Key source paths

- `Ax_analysis/README.md`
- `Ax_analysis/codex/README.md`, `laws.md`, `playbook.md`
- `Ax_analysis/capture_forced.py`, per-app full/forced captures
- `atree/AGENTS.md`, `core/snapshot.py`, `core/axdiff.py`
- `atree_v2/theoratically.md`
- `arc-cua/LATENCY_IMPROVEMENT.md`, `src/arc_cua/backends/macos_ax.py`
- `lsfg/reasoning.md`, `src/lsfg/plan/digest.py`, `src/lsfg/ax/identity.py`
- `agent-desktop/CONCEPTS.md`, compact/skeleton implementation plans
- `vlm_testing/click_groq_fast/benchmark_snap_atree.py`, matching logs
