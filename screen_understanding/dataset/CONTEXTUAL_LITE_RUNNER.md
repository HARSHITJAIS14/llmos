# Contextual annotation with the available Flash Lite models

Use `scripts/run_contextual_lite.py`. This is a bounded replacement experiment for `run_dual_flash_annotation.py`; old captures, detections and annotations are preserved. No paid-tier upgrade or different teacher is required.

## What changed

- Both existing models remain available: gemini-3.5-flash-lite and gemini-3.1-flash-lite. The run records actual returned model versions. No high-thinking setting is claimed for this experiment; provider defaults apply.
- One clean-image pass describes meaningful regions and groups, including content. A normalized 0–1000 coordinate convention applies only to these newly proposed regions; code maps them to source pixels.
- Existing detector boxes are grouped spatially into chunks of at most 20. Each request receives a clean whole-screen overview, clean detailed crop and separate ID overlay. Descriptions and context are requested for every candidate separately.
- The teacher does not regenerate detector coordinates. Source geometry is preserved exactly for those nodes.
- JSON Schema constrains output. Local checks enforce exact candidate-ID coverage, legal categories, valid region parents, positive in-bounds geometry, unique node IDs, one root, acyclic hierarchy and bidirectional proposal correspondence.
- Missing candidates fail the stage. Unknown parents and spatially inconsistent parents remain unresolved. Root fallback is forbidden. False/duplicate detections may be rejected with explicit evidence.
- Multiple region/chunk requests use a bounded worker pool. Per-model start spacing limits RPM. A request-attempt budget bounds the experiment. No automatic retries spend requests silently.
- Raw responses, finish reasons, actual model versions, token usage, timing, prompts, image hashes and schemas are retained. Cache keys include these request inputs. A file lock prevents two concurrent writers to the same output directory.
- A human-readable HTML report provides separate region and element overlays plus descriptions, context and every disposition.

## Run a small test

From `/Users/harshit/Desktop/YC`:

```bash
/Users/harshit/miniconda3/bin/python \
  screen_understanding/dataset/scripts/run_contextual_lite.py \
  --output screen_understanding/dataset/contextual_lite_runs/NEW_RUN \
  --screens screen_0001 screen_0002 \
  --workers 2 --chunk-size 20 --rpm 10 --max-calls 12
```

The environment already has Pillow, jsonschema, google-genai and python-dotenv. Keys are loaded from the existing project dotenv file without printing them. Running the same configuration/output directory reuses validated content-addressed responses. Changed request settings invalidate their cache. Failed responses are preserved; reattempting an identical failed request currently replaces that request's failed response file, so use a new run directory when retaining every failed attempt is required.

`--daily-budget` defaults to 12 attempts per model in that output directory's ledger for the UTC day. This is a conservative **local allowance**, not account-wide provider-quota enforcement. It cannot know calls from Antigravity, older scripts or other output directories, and UTC need not match the provider reset timezone. Deduct other usage and leave headroom. The worker count is not an RPM or tokens-per-minute allowance. Stop/reduce concurrency if the provider rejects requests.

With 51 boxes and chunk size 20, a screen needs four calls: one region request plus three detailed requests. With 83 boxes it needs six. Consequently, 1,000 available requests do not support 1,000 fully annotated screens using this approach. Fewer carefully annotated screens are preferable to pretending every box is labeled. Deduplicate similar capture states before spending quota; preserve intentional state changes and capture-group splits.

## Deliberate limits

All outputs are unreviewed and coverage remains incomplete pending human coverage audit. This version collects region and individual-proposal context, not exhaustive exact-text transcription, missing leaf discovery, split/merge repair, temporal correspondence or a separate semantic audit. Do not promote the output to final ground truth based on structural validation alone.

Region geometry and the meaning assigned to detector boxes can still be wrong. Parent overlap checks flag obvious inconsistencies but do not prove parent semantics. Detector proposals containing multiple unrelated elements should be unresolved, not forced into one label. Rejected proposals and descriptive claims need visual review.

The first tests use two views of the same System Settings panel. They test pipeline correctness and annotation detail, not generalization across macOS applications. Evaluate additional screened application families before expanding.

Run validation tests with:

```bash
/Users/harshit/miniconda3/bin/python -m unittest discover \
  -s screen_understanding/dataset/scripts/tests
```

## Measured pilot outcome (2026-10-18)

Reports: `contextual_lite_runs/pilot-02/screen_0001/report.html` and `contextual_lite_runs/pilot-02/screen_0002/report.html`.

| Screen / teacher | Previous nodes | Revised nodes | Proposal dispositions |
|---|---:|---:|---|
| 0001 / 3.5 Flash Lite | 3 | 58 (root + 6 regions + 51 elements) | 51 retained, 0 unresolved |
| 0002 / 3.1 Flash Lite | 4 | 90 (root + 9 regions + 80 elements) | 77 retained, 6 unresolved |

Three screen-0002 nodes are preserved for inspection but their dispositions are unresolved because parent geometry is inconsistent. Three more candidates have unknown teacher-returned parent IDs; their raw predictions and context are retained in response files and disposition reasons. They are not attached to invented/root parents.

JSON-mode-only testing produced malformed JSON. The first large constrained schema was rejected with HTTP 400. The working schema constrains basic structure and types; exact IDs, enumerations, coverage and hierarchy are checked locally. Unknown parent IDs are explicitly quarantined as unresolved, with original claims preserved, rather than causing otherwise valid chunks to be lost. Existing structurally complete raw responses can be revalidated offline without new API requests.

Screen 0001's detailed pass took 18.22 seconds using a cached global pass; the recorded global request took 4.39 seconds separately. Screen 0002's selected successful API calls took 3.97–11.35 seconds each. Development retries and schema failures were additional work. No fresh whole-pipeline throughput benchmark was completed; final reports were rebuilt offline, so their subsecond replay times are **not inference latency**. `api_seconds` lists the original request timings and `cache_hits` makes reuse explicit. All attempts are recorded in each run directory's ledger.

Visual spot-check: screen 0001's sidebar labels, theme swatches and icon-style controls now have individual contextual descriptions. However, selected-state predictions incorrectly mark Auto appearance selected and Dark unselected. This is a known label error, not fixed ground truth. Screen 0002's global output also calls the Stage Manager thumbnail area “Dock/Desktop Stacks”; it needs review. Structural validity does not establish semantic accuracy. Both screens show essentially the same application state, so broader application evaluation remains necessary.

To rebuild reports without any new requests, append `--offline` to the command with the same output and input settings. A missing/invalid cache fails instead of calling the provider.
