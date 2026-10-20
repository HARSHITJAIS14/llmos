# Notion live mapping test

Tested the user's existing LLM OS page with an open database side peek, without editing its content. Mapping uses the identical `ax-entities-v1` hash recorded in the earlier cross-app comparison. No Notion-specific box edits or canonicalization rules were introduced.

Open `comparison/notion/index.html` to toggle all raw projected nodes and canonical controls, inspect labels/context, and download the entity graph. `comparison/notion/controls.png` is the labeled screenshot.

## Results

- 717 in-window AX nodes reduced to 504 entities; 213 nested-node reductions retain original membership and refs.
- 176 control candidates, including 66 with unresolved high-overlap relationships. These are heuristic ambiguity flags, not independently adjudicated errors.
- Mapping/canonicalization: about 18 ms median / 19 ms p95 over 20 local runs. This excludes AX IPC and screenshot capture.
- Measured AX reads took about 563 ms before and 458 ms after the screenshot; screenshot capture took about 159 ms. Their combined measured work is about 1.18 seconds, before other capture checks. The complete pipeline is not sub-500 ms.
- Capture rejected by the current guard: approximately 483 ms timestamp skew versus the 250 ms policy, and a changed visible AX fingerprint. The guard was not relaxed to obtain a pass.
- Visual inspection supports alignment of sidebar rows, page headings, project cards and side-peek property controls. This is not a precision/recall benchmark or an action-success test.

## Capture and traversal limitations discovered

1. The original depth-14 read captured just 70 nodes and left 11 frontiers, omitting substantial page content. That failed attempt and its deeper diagnostic remain in `../notion-live-01/`. A depth-30 diagnostic captured 1,176 nodes, reached depth 29 and reported no remaining child frontiers. The paired capture used depth 30 as well. Capture depth changed in response to observed truncation; mapping rules did not change.
2. Exact-window screenshots failed with “could not create image from window” despite granted permissions and a readable AX window. CUA's Raise/capture path also failed. A fallback captured only the known Notion screen rectangle after the user brought it forward. Notion's PID was checked as frontmost both before and after. Window/process geometry stayed unchanged, and the AX root rectangle equaled the capture rectangle.
3. This is a screen-region image, so floating occluders remain possible. The screenshot visibly includes the desktop pet over part of the side peek. There is no claim of pixel-level occlusion handling.
4. The before/after comparison recorded six attribute/child-count differences in `changes.json`. A visible native image labeled “Change page icon” became an “Open” button with different supported actions and slightly different geometry. Position-path-based identity is not sufficient through that mutation. Native snapshot refs must be refreshed and revalidated at execution.

## Assessment

Notion exposes useful native semantics, and the deterministic coordinate projection aligns meaningfully with its UI. The current normalization is not sufficient to declare a reliable general action map: deep traversal is required, overlap ambiguity is substantial, dynamic/hover controls mutate, occlusion remains unhandled, and capture dominates latency. Preserve uncertainty and use the screenshot alongside AX context; do not force one node per visible object or treat a clean overlay as evidence of correctness.
