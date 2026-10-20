# Cross-app AX projection and nesting test

Date: 2026-10-19. Six app attempts, three paired captures, including the previous Finder baseline. This is a diagnostic of native geometry, nesting and capture failures, not a labeled accuracy benchmark.

Open `comparison/index.html` for identical-rule overlays and raw projected layers. `comparison/summary.json` contains measurements, capture checks, limitations and the hashes of the algorithms used.

| Surface | Projected nodes | Canonical entities | Control candidates | Unresolved overlapping controls | Capture result |
|---|---:|---:|---:|---:|---|
| Finder YC folder (earlier capture) | 216 | 195 | 55 | 8 | No bracket change detected; action freshness unverified |
| Calculator basic keypad | 35 | 30 | 25 | 0 | No bracket change detected; action freshness unverified |
| System Settings Appearance | 131 | 103 | 53 | 0 | Visible fingerprint stable, but blocked by 285 ms skew exceeding current 250 ms policy |
| Safari controlled nested-form fixture | — | — | — | — | Exact-window AX capture rejected, including an isolated-window retry |
| Antigravity IDE / Electron | — | — | — | — | Exact-window AX capture rejected |
| TextEdit | — | — | — | — | Desktop tool failed with ScreenCaptureKit -3811; no paired capture |

Counts describe output records, not precision, recall or coverage. No visual detector/OCR proposal mapping was benchmarked on these live captures. The optional visual association path is implemented and has fixture tests, but needs independently labeled live proposal correspondences.

## What visual inspection supports

Inspected all three generated control PNGs. Calculator's keypad and toolbar bounds align with the rendered controls. Settings' sidebar, appearance options, color choices, menus and switches align at the captured geometry. Finder's sidebar and file rows align, but headers and nested control candidates retain overlap ambiguity. No hand-edited bounds or per-app cleanup were used by the new algorithm.

The original Finder display filter was also run unchanged on Calculator and Settings; those results remain in their `review/` directories. It is a visualization heuristic, not an identity algorithm. In particular, equal bounds alone cannot justify deleting nodes. The new canonicalizer is more conservative and therefore sometimes less visually sparse.

Settings' before/after full-tree difference was traced to five bounds changes in sidebar nodes below the window capture. Its visible fingerprint remained equal. The original capture, timing rejection and full-tree mismatch were retained; an added analysis frame records the viewport comparison. The skew limit was not relaxed to obtain a passing result.

## Algorithm implemented after the diagnostic

`../../canonicalize.py`, version `ax-entities-v1`, uses the same rules for every app:

1. Require an explicit capture transform and retain capture validation failures.
2. Preserve the complete input-node list, parent hierarchy and snapshot refs. Only positive-area projected nodes participate in spatial canonicalization.
3. Coalesce ancestor/descendant nodes only when IoU is at least .85 and a member is a wrapper/label, with no conflicting native labels, meaningful control roles, explicit state opposites or nonempty values. Every merge has a reason and original membership.
4. Never coalesce siblings merely because their rectangles or names match. Repeated labels keep their named ancestor context.
5. Prefer an explicit control as the primary member; preserve actions on their originating raw nodes. A table/list wrapper containing distinct child controls becomes context rather than another primary control. Content-only cells are not classified as controls.
6. Flag remaining control overlaps at IoU .8; do not force a resolution. These thresholds are heuristics, not calibrated confidence.
7. Optionally associate screenshot detector/OCR regions using the existing overlap/text evidence ranking against these entities. Require a score and margin; return ambiguous/unmatched/blocked where appropriate. Generated captions do not become OCR truth. Relationships can be many-to-one.
8. Refuse action authorization. Even an apparently stable capture needs live visibility, enabled state, identity and action-specific validation at execution.

Conservation check: all three captures retain 100% of projected-node membership in the entity graph. This measures traceability, not correctness of the merges.

## Timing and tests

Twenty repeated local runs including normalization and canonicalization, excluding screenshot/AX IPC and downstream inference:

- Finder: about 3.4 ms median / 4.2 ms p95.
- Calculator: about .36 ms median / .68 ms p95.
- Settings: about 1.8 ms median / 2.2 ms p95.

The 25 tests cover coordinate transforms and matching plus nested equivalence, sibling ambiguity, role/label/state/value conflicts, repeated-label context, raw-action preservation, content cells and capture rejection. These tests do not establish universal semantic accuracy.

## Collector limitations and privacy

The existing agent-desktop resolver contains an `AXWindow` role requirement. Earlier lsfg research explicitly discusses focused/main windows and alternative roles on some surfaces. That is a plausible source of the Safari/Electron failures, not a proven diagnosis of these particular windows: the root roles were not independently recorded here. CUA could read both apps' trees, so the failures do not establish an absence of AX data. Fix and validate exact-window collection before claiming browser/Electron coverage. Do not substitute nearest-window guessing.

Automatic approval review rejected a proposed app-scoped Safari diagnostic because it could include private IITK webmail outside the local-fixture test. That command did not run. Testing then stayed with exact fixture-window IDs; no app-wide Safari snapshot was persisted.

The Safari fixture is an authored local page with two Save buttons in different groups, nested containers, a disabled control, checkbox state, an accessible icon label and canvas text without an individual AX node. It is a controlled test surface, not a natural browser-screen benchmark. Its paired capture failed, so it contributes no live mapping accuracy evidence.

Conclusion: projection and conservative nesting reduction are promising on these native captures. Reliable general mapping is not established. Resolve exact-window acquisition, then measure accepted-link precision, abstention and visual coverage on labeled native/web/Electron pairs before integrating it as trusted agent perception.
