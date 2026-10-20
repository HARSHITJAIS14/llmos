# Pilot automation review — 2026-10-18

## Findings from the existing files

This is a code/artifact inspection, not a full visual audit or independent verification of screenshot capture authenticity. Preserve the existing pilot as development data; do not overwrite it during repairs.

- 30 reviewed annotation files contain 342 nodes and 1,235 proposal dispositions.
- 168 nodes have generic context strings beginning `Located inside `.
- All 30 teacher/reviewed file pairs are byte-identical. This does not prove no review occurred, but it supplies no correction history.
- 29 annotations claim human review. `annotate_real_screen.py` sets human_reviewed and audit_applied to true automatically, and make_node defaults to reviewed_correct. These flags are not evidence of actual human review.
- Unclaimed proposals are automatically attached to an enclosing node and marked retained. This accounts for proposals without necessarily describing the detected element. Zero unresolved proposals does not demonstrate semantic completeness.
- Only five response files were found under the screen response directories, and usage.jsonl has two entries. Full scripted-teacher request timing/cost provenance is unavailable for this pilot; Antigravity interaction costs are not captured by these files.
- `build_full_pilot.py` still contains synthetic image generation. Its presence does not establish that current source files are synthetic, but it must not be invoked for the real-only capture workflow.

## Confirmed sources of avoidable overhead

`detector.py` copies one image, starts SSH/Python, imports libraries, hashes and loads the checkpoint, predicts one image, copies JSON back and performs remote cleanup for each screen. The earlier 58 ms warm detector timing excludes this startup/transfer work and is not a measured pilot end-to-end rate.

`pipeline.py` processes screens sequentially and then each discovered region sequentially. Antigravity additionally constructing annotations through scripts incurs interactive-agent overhead. Exact time attribution cannot be calculated from the current incomplete logs.

`gemini_teacher.py` reuses cache files by name without verifying the current prompt, image or schema hash. Simply making the current code parallel would retain correctness problems.

## Implementation handoff: automate the pipeline, retain contextual quality

1. Keep capture and annotation separate. Capture curated, safe native states once into an immutable, hashed manifest. Use real capture groups rather than declaring every screenshot a separate session. Reuse these images for reruns; do not repeatedly navigate apps to relabel them.
2. Transfer eligible images together. Run one GPU worker that loads the detector once and processes the manifest, retaining per-image timings and model/image hashes. A persistent process is sufficient; large GPU batches are optional and must be measured.
3. Run a resumable teacher queue outside Antigravity's conversational loop. Antigravity implements and supervises the scripts; explicitly configured Gemini 3.8 Flash/high API calls perform the annotation. IDE access and API access are separate.
4. Start with four global API workers, bounded by the actual request/token quotas. Each screen has a global pass, contextual region/chunk passes and an audit. After its global pass, independent regions may run concurrently. Use one shared global concurrency limit so region workers do not multiply request load unexpectedly.
5. Assign disjoint node-ID namespaces per screen/region. Merge deterministically after calls complete, reconcile duplicates and relationships, and then audit. Never share mutable per-screen annotations between concurrent requests.
6. Start with 10–25 nearby elements per request, including clean global and parent context. Process all meaningful areas, not just icons. Only request additional crops for unresolved details; avoid repeatedly annotating overlapping whole windows and their child regions.
7. Cache by screenshot/crop hash, detector configuration, model/thinking settings, prompt and schema version. Save every response attempt, finish reason, usage and timing. Atomically commit valid stage outputs; use bounded retries and separate failure records.
8. Preserve unmatched proposals as unresolved. Retained means an actual corresponding annotation exists; containment is a separate relation. Generate meaningful region and leaf context instead of filling parent-ID strings. Preserve unknown functions where genuinely unsupported.
9. Set human_reviewed=false unless a recorded human review event exists. Keep teacher audit separate from human review. Do not fabricate confidence or returned model identity. Run geometry and semantic consistency checks independently of schema validation.
10. Test on three existing, screened pilot images in a new run directory. Compare against manually reviewed targets and record wall time, API wait, retries, token usage, throughput and errors. Then process all 30. Do not expand to 3,000 until the pilot quality gate is met and the user approves expansion.

## Measure the right speed

Report capture time, detector startup, transfer, warm detection, teacher work per screen, queue wall time, validation time and human correction time separately. Report both per-screen latency and whole-dataset throughput.

Estimate scale from measured accepted screens/hour and correction minutes/screen. Concurrency can improve throughput but does not make each API inference faster, and four workers do not guarantee a fourfold improvement. Dataset annotation does not need to satisfy the eventual student's 500 ms inference target.

## Status

The capture/proposal work is useful. Current artifacts do not establish fully reviewed contextual ground truth or readiness for production expansion. No images were changed, uploaded or relabeled during this inspection. No new dataset run was started.
