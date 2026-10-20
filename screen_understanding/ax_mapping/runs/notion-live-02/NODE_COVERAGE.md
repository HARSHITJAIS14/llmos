# AX nodes without a verified visual counterpart

The 504 entities reported earlier are groups derived from native AX records, not independently verified visual objects. The screenshot was inspected for broad alignment, but no complete detector/OCR/manual correspondence ground truth exists for this capture. Therefore the number of AX nodes with a confirmed visual match is unknown.

An audit of the saved 1,170-node Notion capture found:

| Exclusive geometry/metadata category | Nodes |
|---|---:|
| Explicitly marked hidden/invisible/offscreen in AX states | 443 |
| Not hidden by metadata, but invalid bounds (zero height) | 10 |
| Positive-area bounds projected inside the captured rectangle; visual correspondence unverified | 717 |

The last category yields 176 control candidates, of which 66 have overlapping control ambiguity, 36 lack a normalized label, 35 are at most two physical pixels thick and three are marked disabled. These risk counts overlap. An unnamed control is not necessarily invisible; an icon can be recognizable in the image. Positive bounds likewise do not establish visibility.

Concrete thin-control examples include:

- `Skip to content`: 360 × 2 screenshot pixels.
- Two `Open shortcut menu` comboboxes: 2 × 2 pixels each.
- A `Private` section control and several page rows: 458 × 2 pixels.

These nodes still expose native actions such as Click, Expand and SetFocus. The existence of an action is not evidence of a usable visual click target. One zero-height group also exposes Click. Native semantic actions can still affect UI that has no currently usable visible target, so replacing coordinate clicks with AX actions does not settle target validity.

The current entity mapper excludes hidden/invalid nodes from spatial association but retains them in the source graph. It does not yet enforce visual confirmation or a minimum click-target size for every remaining control candidate. All outputs already set `action_authorized: false`, and this capture is blocked for timing and visible AX mutation. This is an analysis prototype, not a safe action executor.

For workflow integration, supply a separate validated target list rather than the full AX graph as executable choices. Hidden, degenerate, ambiguous, disabled and stale records must not become automatic coordinate targets. Retain them as context or unresolved records; reveal by an appropriate scroll/expand step and recapture when the task requires them. For unnamed/icon controls or uncertain visibility, use screenshot evidence. Validate the current node identity, supported action and visible state immediately before execution, and verify the resulting state afterward. Unknown remains unknown; do not force a nearest-node match.

See `node_coverage_audit.json` for exact node IDs, snapshot refs and examples. No new live capture, external API call or UI action was used in this audit.
