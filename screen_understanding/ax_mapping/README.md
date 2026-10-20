# Screenshot ↔ accessibility mapping prototype

Latest: [screen-map-v1 implementation](SCREEN_MAPPING.md) and [independent image-evidence inspector](runs/screen-map-v1/index.html). This adds image OCR/shape support, one disposition per AX record, bidirectional links and explicit excluded/unresolved records. It is an analysis prototype; live action validation is not implemented.

## Cross-app diagnostic and conservative nesting algorithm

The follow-up six-app diagnostic is in [runs/cross-app-01/RESULTS.md](runs/cross-app-01/RESULTS.md), with an [interactive comparison](runs/cross-app-01/comparison/index.html). Three paired captures were obtained; other capture failures are retained. General reliability is not established.

`canonicalize.py` adds app-independent entity grouping with lossless raw-node membership, conservative nested-node merging, ancestor context and unresolved-overlap flags. It does not delete equal-geometry siblings or automatically authorize actions. With `--regions`, it also runs optional screenshot-region association against these entities. The simpler `matcher.py` below remains the original baseline.

```bash
python3 screen_understanding/ax_mapping/canonicalize.py \
  --ax /absolute/path/snapshot.json --frame /absolute/path/frame.json \
  --regions /absolute/path/proposals.json --out /absolute/path/mapping.json
```

Omit `--regions` to export the native entity graph alone. Input bounds and capture metadata follow the format below. Live cross-app validation currently covers native projection/canonicalization, not labeled detector-to-AX correspondence accuracy.

The practical approach is a **spatial association graph**. Native AX already supplies labels, roles, state, supported actions and rectangles. Project those rectangles into the screenshot, and associate detector/OCR regions with them. Preserve the full image for visual reasoning. A new captioning model is unnecessary for this association step.

This implementation reuses saved agent-desktop observations. It does not replace the existing AX capture, lsfg digest, atree scoped expansion, identity or action verification components. See [the workspace research audit](../research/2026-10-19-existing-ax-work-review.md).

## Pipeline

1. Capture the screenshot and AX observation close together. Record the actual capture rectangle in global logical points, image dimensions, window identity and capture times. Prefer one window/display with a known transform. Record before/after capture identities or signatures to detect intervening changes. Merely taking two observations close together does not guarantee synchronization.
2. Project native AX rectangles to screenshot pixels. For one unpadded image, `pixel_x = (ax_x - capture_x) * image_width / capture_width`. Do the corresponding calculation for y. For a resized/padded image use the content rectangle instead. There is no universal Retina division by two. AX uses global top-left coordinates; convert other coordinate conventions before calling this code. Window shadows and crop borders must be accounted for in capture metadata.
3. Remove explicitly hidden nodes, invalid geometry and nodes outside the capture. Keep hierarchy and evidence of unexpanded children. Geometry alone cannot establish visibility through another window or clipping ancestor; capture visibility/occlusion validation remains the caller's responsibility.
4. Compare each visual region against overlapping AX nodes. Gate out weak overlap, extreme area/aspect ratios and tiny regions swallowed by broad structural ancestors. Rank remaining candidates by region coverage, IoU and size similarity, with optional observed OCR agreement and role agreement. Current weights and thresholds are hand-set starting points, not learned or calibrated confidence.
5. Return a correspondence only above a score threshold and a margin over the next candidate. Keep ambiguous candidates instead of forcing an answer. Equal-geometry parent/child wrappers often remain ambiguous; a future verified canonicalization can collapse equivalent wrappers while preserving their refs. Do not force one-to-one assignment: an icon and its adjacent text can both correspond to one native button.
6. Keep **containment** separate from correspondence. A panel can contain ten AX controls without itself being any of those controls. Parent IDs preserve their native hierarchy. The nearest ancestor with supported actions is returned as evidence, not as an authorized click target; its action may be Scroll rather than Click.
7. Build a compact downstream observation using existing digest logic: stable local region alias, pixel rectangle, native role/name/state, snapshot-qualified AX reference, parent context, and association status. Show screenshot plus these useful records, rather than the full raw tree. For example, a matched row might become `R17 checkbox "Show hidden files" checked [x1,y1,x2,y2] source=AX`. Only add states actually observed.
8. Preserve unmatched visual regions as visual evidence. Preserve unassociated AX nodes for scoped inspection; an unassociated node is not proof that it is invisible or missing from the screenshot. The output caps these records at 50 and containment records at 20, with total counts. Do not invent native semantics for a visual-only region.

For a rich native surface, start by drawing IDs directly on projected AX boxes. Detector proposals are useful for AX gaps and for relating existing visual regions to native nodes; they are not required to rediscover all native controls. OCR is optional and generated micro-captions do not count as OCR evidence. Canvas, PDF contents, charts and custom-rendered UI still need visual interpretation.

## Implementation and use

`matcher.py` is a pure standard-library module. It accepts the existing agent-desktop nested snapshot envelope (`data.tree`) or a raw nested tree. Each native bound is `{x, y, width, height}`. Adapters for lsfg flat snapshots and atree sidecars are not implemented yet; they must preserve native identity, parentage and capture metadata rather than infer them from a screenshot.

Visual input is a list, or an existing `{"proposals": [...]}` envelope:

```json
[{"id": "d_0001", "bbox": [120, 80, 160, 120], "ocr_text": "Save"}]
```

All visual rectangles use pixel **xyxy**, not normalized coordinates. `ocr_text` and `role` are optional. Model-generated descriptions are deliberately ignored when scoring.

Frame metadata example (illustrative values; obtain these from the capture):

```json
{
  "capture_bounds": {"x": 100, "y": 50, "width": 800, "height": 600},
  "image_size": [1600, 1200],
  "ax_origin": "top_left",
  "screenshot_time": 1792400000.01,
  "ax_time": 1792400000.03,
  "max_skew_ms": 250,
  "screenshot_window_id": 42,
  "ax_window_id": 42,
  "ax_snapshot_id": "s_actual_snapshot_id"
}
```

Optional `content_rect: [x1,y1,x2,y2]` describes the unpadded image area. Mixed-scale multi-monitor captures must be split into calibrated frames; the prototype rejects `mixed_scale_displays: true`. The 250 ms skew default is a configurable rejection policy, not a measured guarantee of UI stability. Identity/time mismatches block associations. Missing metadata or close timestamps do not establish freshness: the frame remains `unverified`, and every output has `action_authorized: false`. Revalidate current identity, geometry, visibility, enabled state and the specific supported action before any execution.

From the YC workspace:

```bash
python3 screen_understanding/ax_mapping/matcher.py \
  --ax /absolute/path/snapshot.json \
  --regions /absolute/path/proposals.json \
  --frame /absolute/path/frame.json \
  --out /absolute/path/mapping.json

python3 -m unittest discover -s screen_understanding/ax_mapping -p 'test_*.py' -v
python3 screen_understanding/ax_mapping/benchmark.py
```

The result includes matched/ambiguous/unmatched regions, candidate evidence, native ancestry, containment, unassociated AX nodes, capture checks and truncation/frontier information. Paths such as `0.2.1` are local to this observation; they are not persistent element identities. Native refs must remain associated with their original snapshot. No clicking, external API calls, training or desktop mutation occurs.

## Verification and measured cost

The initial 16 tests cover coordinate transforms at 1×/2× and unequal scales, padding and negative origins, ambiguous duplicates, OCR disambiguation, ignored generated captions, parent actions, many-to-one correspondence, no-overlap rejection, sliver rejection, hidden ancestry, capture mismatches, invalid geometry and missing children. A saved Finder tree exercises the real input adapter. These are correctness fixtures, not a real-screen accuracy benchmark.

`benchmark.json` records a local 30-sample timing diagnostic at 1/8/32/50 regions. The fixture has 1,571 AX nodes, of which 61 intersect the diagnostic frame. **Visual regions are synthesized from AX bounds**; no synchronized screenshot was found for that old capture. The root rectangle is used only to construct this diagnostic frame. The ambiguity counts in that file are not accuracy scores.

The recorded run took about **4 ms median / 6 ms p95 for 50 regions**, including flattening/projection, on this Mac. This excludes screenshot capture, AX IPC, detector/OCR, JSON file I/O, image encoding and network/model time. It establishes that this small association step is cheap on this fixture; it establishes neither a 500 ms end-to-end bound nor general accuracy. Complexity is currently O(visual regions × visible AX nodes), plus flattening; introduce spatial indexing only if dense live captures justify it.

## Next validation before trusting it

Collect synchronized pairs from Finder, Settings, a browser, VS Code and an opaque/custom-rendered app. Include scrolled views, popups, repeated labels, occlusion and multiple displays. Manually mark a small set of true links and genuinely missing/ambiguous regions. Measure accepted-link precision, correspondence coverage, abstention rate, capture skew and total observation latency. High precision with explicit abstention comes before increasing coverage.

Then compare screenshot-only with screenshot + native AX digest on the same held-out tasks and prompts. Measure target selection, state-change detection and actual verified outcomes. The earlier micro-caption ablation does not answer whether native AX labels, states and supported actions help. No new model training is required for this test.
