# Screenshot/AX association: implementation and evidence

`screen_map.py` implements an evidence graph using all AX records, a calibrated screenshot and independent image proposals. It does not invoke a language model, move the cursor or execute actions. `runs/screen-map-v1/index.html` shows the same algorithm on four saved captures.

## What the available CUA interface does

The desktop tool exposes AX state, screenshots, native element-index operations and coordinate operations. A target selected by an AX index and a target selected by a screenshot coordinate use different addressing paths. The exposed interface does not establish how its underlying perception model was trained or make its indices permanent. This implementation uses only inspectable native data and image evidence; it makes no claim to reproduce the tool's internal model.

## Inputs and output

Inputs are a nested agent-desktop AX observation; actual screenshot bytes/dimensions; capture metadata as defined in README.md; and independent visual proposals. Image hashes and dimensions must match. The saved capture hash is checked too. Coordinate conversion uses capture origin and measured scale; it never assumes Retina means divide by two.

Output contains one record per original AX node, including hidden/invalid nodes, with snapshot-scoped reference, role, label, value, states, parent context, advertised actions, capabilities, pixel bounds, visual evidence links and explicit exclusion/review reasons. It also contains the reverse links from image regions to AX records and image regions without accepted links. No node is silently lost.

Four record dispositions:

- `visually_supported`: an interaction candidate has independent text/boundary support and passed the implemented per-record filters. This is not a certified visible click target.
- `unresolved`: the node may matter, but visibility, semantics, overlap, reference or size evidence is insufficient.
- `context_only`: readable/structural information or secondary/reveal capability, rather than an ordinary primary interaction target.
- `excluded`: hidden/unprojectable, disabled, too thin or outside an ancestor scrollport. The source record remains available with the reason.

`candidate_targets` coalesces supported bindings by canonical entity while preserving original action refs. Different refs are not arbitrarily treated as interchangeable. `executable_targets` is empty: there is no live hit-test/action executor in this module. All top-level, record and group `action_authorized` values are false. A blocked/stale capture remains blocked even when diagnostic visual associations are available.

## Algorithm

1. Preserve and project AX nodes. Retain incomplete-tree/frontier information in the upstream canonical graph. Use its conservative nested-node grouping and named ancestor context; never merge equal-geometry siblings solely by proximity.
2. Separate ordinary Click/Press, edit, select and scrolling capabilities from RightClick, ScrollTo and SetFocus. Snapshot-exported actions may include tool fallbacks; they are not certified native delivery. Many readable nodes advertise RightClick/ScrollTo, so those attributes alone must not make a primary click target.
3. Reject hidden/unprojectable, disabled and less-than-three-logical-point-thick candidates from visible coordinate targeting. Flag substantial clipping, unknown refs, unnamed targets, broad interaction surfaces and unresolved entity overlaps. Mark structural nodes with a Click capability for review instead of assuming their enclosing rectangle is a discrete control. Preserve reveal/secondary capabilities as context.
4. Independently extract image text using existing lsfg Apple Vision OCR. Match a label only if observed text overlaps at least 70% of its own area with the AX box and token similarity is at least .5, with OCR confidence at least .45. Fast OCR confidence is not calibrated correctness. A label can occur in multiple records; return all supported relations, not a forced one-to-one assignment.
5. Independently propose shapes using closed image contours. These are generic pixel shapes, not UI-control detections. Require IoU >= .75 before attaching boundary support. This can support an icon-only native control's geometry but cannot validate its meaning or distinguish a control from matching decoration. Apply the same contrast/size rules to every app. A trained UI detector can supply `control_proposal` inputs instead; that path requires IoU >= .6 and detector confidence >= .6.
6. Attach source IDs, overlap measurements, text similarity and ranking score to each correspondence. Scores are heuristics. Preserve zero-match image regions as unexplained evidence; they may be decoration, ordinary text, OCR mistakes or genuinely missing controls.
7. Group supported candidates for a compact agent interface. Preserve excluded/unresolved/context records separately. Match every original record to a disposition rather than pretending to match every record to a visible object.

Thresholds are conservative prototype rules, not trained or calibrated accuracy bounds. They need labeled evaluation. The mapper does not infer icon semantics from shape contours, determine pixel occlusion, resolve every nested control or prove native hit-test ownership.

## Required live integration

A workflow executor must bind a current native element to the selected snapshot reference, recheck the actual supported action and enabled state, and validate point ownership if delivering coordinate input. A native `AXUIElementCopyElementAtPosition` query can help test ownership without moving the cursor, but it must run in the current capture session with live references and window identity. It is not implemented or measured here. A container hit is insufficient evidence that a particular child control owns a point.

Refresh/reveal targets whose visible representation is missing or ambiguous; do not pick the nearest surviving node. Verify the resulting state after execution. Native identity, hover controls, app updates and animations can change between observation and delivery. Successful OCR or an old AX ref must not override a failed capture guard.

## Run

Using the existing dependencies in this workspace:

```bash
lsfg/.venv/bin/python screen_understanding/ax_mapping/extract_visual_text.py \
  --image /absolute/path/capture.png --out /absolute/path/ocr.json

/Users/harshit/miniconda3/bin/python screen_understanding/ax_mapping/screen_map.py \
  --ax /absolute/path/ax.json --frame /absolute/path/frame.json \
  --image /absolute/path/capture.png --visual /absolute/path/visual.json \
  --out /absolute/path/mapping.json

python3 -m unittest discover -s screen_understanding/ax_mapping -p 'test_*.py'

/Users/harshit/miniconda3/bin/python screen_understanding/ax_mapping/run_saved_validation.py
```

`run_saved_validation.py` extracts text/shapes and builds the visual envelope for the four existing captures; it does not perform live desktop capture. `extract_shapes.py` can export contour proposals independently. `render_screen_map.py` generates the interactive bidirectional evidence inspector.

A visual envelope is:

```json
{
  "image_sha256": "actual sha256 of screenshot bytes",
  "image_size": [1600, 1200],
  "source": "independent image-only provider",
  "items": [
    {"id": "T001", "kind": "text", "bbox": [100, 100, 180, 125], "text": "Save", "confidence": 0.9},
    {"id": "D001", "kind": "control_proposal", "bbox": [90, 90, 190, 140], "confidence": 0.9}
  ]
}
```

Boxes are screenshot pixel xyxy. Providers must not derive their proposals from the AX bounds being evaluated. Proposals copied from AX cannot establish independent visual correspondence.

## Measured diagnostic results

The fixed pipeline was run on saved Notion, Finder, Calculator and Settings captures. The exact measurements and code hashes are in `runs/screen-map-v1/summary.json`; the HTML links each record to image evidence.

| Saved capture | Original AX records | Supported candidate groups | Unresolved records | Saved-image processing wall time |
|---|---:|---:|---:|---:|
| Notion | 1,170 | 50 | 164 | 361 ms |
| Finder | 268 | 27 | 37 | 252 ms |
| Calculator | 35 | 20 | 5 | 207 ms |
| Settings | 199 | 27 | 28 | 266 ms |

All original AX records are accounted for. Supported groups and unresolved records use different units; they are not a percentage or accuracy measure. These are single runs, including OCR subprocess startup, file/evidence handling and mapping; they exclude live screenshot/AX acquisition, hit testing, controller/model inference and report rendering. They establish no worst-case or p95 sub-500 ms claim. In particular, the saved Notion acquisition already took over one second and remains blocked for capture skew/visible mutation; Settings remains blocked for skew. Finder/Calculator capture status is unverified, not authorized.

There is no independently labeled clickable-object benchmark, so visual clickable recall remains null. The generic shape proposals miss controls and include noninteractive objects. The existing GPU detector was unavailable because its hostname did not resolve; no new model was downloaded or trained. Thirty-seven tests cover coordinate transforms, nesting, image identity, independent text/shape evidence, unresolved icons, stale guards, invalid/thin/hidden/disabled nodes, secondary capabilities and structural-node ambiguity. This is an inspectable matching prototype, not a completed general CUA controller.
