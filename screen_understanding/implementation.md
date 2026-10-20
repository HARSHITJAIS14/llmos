# Implementation plan: fast macOS contextual perception on the A40

> **Superseded for execution by the one-day micro-caption plan:** see [training/ONE_DAY_PLAN.md](training/ONE_DAY_PLAN.md). The user has allocated one day to perception and requested at most five generated tokens per box. The longer structured-graph research plan below is retained as background, not the current work schedule.

Date: 2026-10-18

Status: design and implementation specification. The training modules and commands marked **proposed** below do not exist yet. This document does not report new training runs or measured latency. Existing data and environments were inspected locally; current remote GPU availability was not checked for this document.

## 1. Decision and the latency concern

Build a **non-generative contextual screen graph first**. Keep a small VLM as an independently measured enrichment experiment. Do not make fifty generated descriptions a dependency of the 500 ms path.

The previous suggestion that fifty twenty-token descriptions need approximately twenty batched decoding steps was about sequential depth, not total work. The decoder still produces about 1,000 tokens. Its batch size, visual prefixes, vocabulary projection, KV cache, memory traffic, and implementation determine the wall time. It is not justified to infer sub-500 ms completion from twenty steps. Conversely, 1,000 aggregate tokens do not establish a universal one-second lower bound either. Measure the actual workload.

Roles plus OCR are a useful baseline, but insufficient for the original goal. A button named Open, a disabled Open button in a file dialog, and an Open menu item have different context. The first model should therefore provide:

- Boxes for meaningful regions as well as controls.
- Role, surface and content category.
- Observable state, with unknown explicitly represented.
- Parent/child grouping and supported label associations.
- Exact visible text from OCR, with provenance and confidence.
- A contextual embedding trained using our descriptions.
- A small, reviewed vocabulary of contextual categories where data supports it.

This is **structured context**, not arbitrary semantic explanation. An embedding is not a human-readable description and must not be presented as one. A terminal region plus its OCR text does not automatically explain why a command failed. Keep this limitation visible in the product and evaluation.

Use deterministic rendering for facts such as “Open button, disabled appearance, inside file dialog.” Do not claim that templated text is free-form understanding. Optional VLM enrichment can later summarize complex regions, with its own latency and completeness status.

## 2. Data actually available

Authoritative inventory: `dataset/training_inventory/daily_01/README.md`, `inventory.json`, `screens.jsonl`, and `candidate_masks.jsonl`, relative to this document's directory.

| Item | Verified inventory |
|---|---:|
| Annotation files | 190 |
| Distinct decoded screenshots | 163 |
| All nodes | 10,434 |
| Screen roots | 190 |
| Region/group-level nodes | 1,453 |
| Element nodes | 8,791 |
| Candidate non-root nodes after structural exclusions | 9,523 |
| Unresolved proposals | 1,094 |
| Human-reviewed records | 0 |
| Nodes with literal visible-text supervision | 0 |

The candidate count establishes structural eligibility, not semantic correctness. Ten thousand related boxes are not ten thousand independent screen examples. This dataset supports a preliminary fine-tuning experiment, not training general vision or language understanding from scratch.

Source artifacts:

```text
dataset/contextual_lite_runs/full_daily_run/<screen_id>/annotation.json
dataset/contextual_lite_runs/full_daily_run/<screen_id>/source.png
dataset/captures_1000/proposals/<screen_id>.json
dataset/schema/annotation.schema.json
dataset/training_inventory/daily_01/screens.jsonl
dataset/training_inventory/daily_01/candidate_masks.jsonl
```

Inventory paths currently contain absolute Mac paths. The exporter must convert these into paths relative to the exported dataset root. Verify decoded pixel hashes and retain original source metadata; report PNG re-encoding can change file hashes without changing pixels.

## 3. Experiments and decision gates

Implement in this order:

| ID | Pipeline | Question |
|---|---|---|
| B0 | Existing detector + OCR + geometry grouping | What quality and latency do we get without learned semantics? |
| B1 | B0 + local visual role/state heads | What does basic visual recognition add? |
| B2 | B1 + contextual region transformer + relationship/category heads | Does global context improve perception enough to justify its cost? |
| B3 | B2 + description embedding supervision | Does existing contextual prose improve generalization? |
| G1 | Pretrained SmolVLM-256M, short captions on selected regions | What is the real cost and semantic benefit of generation? |

B2/B3 are the intended first student. G1 is not required to make their output available. If the user requires fresh prose for every region within 500 ms, B2/B3 alone do not meet that contract; G1 must independently pass the full-screen test.

Do not spend the week implementing a custom decoder before measuring standard short-caption generation. Do not promote a fast model if it merely reproduces role labels and adds no contextual benefit.

## 4. Student architecture v0

### 4.1 Inputs and coordinate system

- RGB screenshot in original source coordinates.
- Detector proposals, excluding any teacher descriptions, app labels, or hierarchy at inference.
- OCR spans computed from that screenshot.
- No AX tree, application metadata, filenames revealing app state, or teacher boxes at deployment.

For the first benchmark, compare aspect-preserving overview inputs with long side 768 and 1024. Pad to supported encoder dimensions and retain the exact resize/padding transform. These are research settings, not assumed sufficient resolution for tiny icons.

Original-resolution OCR remains separate. Resizing the semantic input does not authorize discarding small text. Later compare a bounded overview-plus-tile variant. Avoid unlimited recursive crops.

### 4.2 Pretrained visual backbone

Start with the SigLIP visual encoder from `HuggingFaceTB/SmolVLM-256M-Instruct`, approximately 93M parameters according to the publisher. Load the actual checkpoint configuration and pin its revision. Verify supported positional-embedding interpolation before using resolutions beyond its training configuration. If unsupported, use the native resolution with fixed tiles; never silently reshape learned positions.

Use dense patch features before the VLM's aggressive visual-token compression. Freeze the backbone initially. We are borrowing pretrained visual features, not assuming they are already optimal GUI region features.

The language decoder is absent from the B1–B3 inference path. Total student size is the visual backbone plus adapters and heads; record the instantiated count rather than quoting the original VLM's 256M total.

If visual encoding alone fails the budget, benchmark a smaller pretrained ConvNeXt-V2 Nano backbone with multiscale features as an alternative. The official Nano is about 15.6M parameters. This is a replacement experiment, not a second encoder added to the pipeline. Different backbone semantics require retraining and quality comparison.

### 4.3 Region feature extraction

For each proposal, sample a 4x4 feature grid inside the box and a second 4x4 grid from a 1.5x expanded box, clipped to the image. Project/pool each to width 256. Add:

- Global image representation.
- Normalized box coordinates, width, height and area.
- OCR geometry and a bounded text representation when available.

Use RoIAlign or equivalent differentiable sampling with an explicit coordinate convention. Unit-test source-to-feature transforms on synthetic rectangles. Expanded boxes must never escape the image. The context transformer sees region vectors, not a separate image encoding per region.

For OCR text, start with geometry/confidence features and an ablation using cached pretrained text embeddings. Cached text features are acceptable during training; live text-encoding latency must be counted during inference. A visual-only contextual variant remains an important baseline. OCR absence must have an explicit mask.

### 4.4 Context transformer

Initial settings: width 256, four layers, eight attention heads, MLP width 1024, dropout 0.1. Inputs include element tokens, region tokens, and a root token. Add box-position embeddings and pairwise geometry bias if the plain model merits further development.

Benchmark 32/64/128-node buckets, with masks for padding. Larger screens must use an explicit overflow policy: report incomplete coverage and queue remaining work, or run a larger bucket with a separately measured service level. Never drop nodes and label the output complete.

### 4.5 Heads and output

| Head | Target | Important restriction |
|---|---|---|
| Role | Reviewed role taxonomy | Preserve unknown and corrected raw roles |
| Surface | Existing surface enum | Do not infer app from dataset filename |
| Content category | Compact reviewed vocabulary | Do not turn every free-text content_type into a class |
| State | Separate selected/checked/expanded/disabled heads | Unreviewed or unknown values have masked loss |
| Parent | Scores over candidate regions plus root | No self-parent; enforce acyclic output |
| Proposal validity | Retained vs clearly rejected | Unresolved is not background |
| Semantic embedding | Description/context embedding | Auxiliary supervision; not a prose output |

Use parent scores and geometry to construct a rooted acyclic graph; log constraint repairs. Do not claim raw neural outputs are guaranteed acyclic. Add label/description relations only where reviewed examples provide sufficient support. Missing relation annotations are not automatically negative examples.

The deployment graph should be a new versioned prediction schema, not fake a fully populated training annotation. Include boxes, field confidence, unknowns, OCR spans, evidence provenance, coverage, timing, and optional enrichment status. Code serializes JSON; the network does not generate JSON syntax.

### 4.6 Region proposal head

Leaf detection does not cover all meaningful areas. Add 32 learned region queries that cross-attend to spatial image features and predict region boxes, objectness, and coarse region role. Train with bipartite matching using annotated window/region/group targets, L1 and generalized-IoU loss, and role loss.

Incomplete annotations make unmatched queries ambiguous. Apply no-object loss only in reviewed regions/screens with adequate coverage; otherwise mask or downweight those targets. The roughly 1,453 region labels are a small starting set, not evidence that this head will generalize immediately.

Train the relationship head with teacher regions initially, then mix in matched predicted regions and proposal jitter. At evaluation, publish both teacher-region diagnostic results and **predicted-region end-to-end results**. Only the latter count as deployment performance. For unmatched predicted regions, mask unavailable semantic targets instead of assigning invented labels.

## 5. Dataset preparation and review

### 5.1 Immutable export

Build a new training export; never modify source annotations in place. Save export version, input hashes, teacher provenance, cleaning rules, and reviewer decisions.

Recover raw roles from cached teacher responses when possible. Current aliasing can map slider to toggle and radio to checkbox. Correct identifiable cases or mask them; do not relabel every checkbox or toggle. Version the training taxonomy independently of the original schema and preserve both original and corrected values.

For each node save per-field masks, not only a blanket valid/invalid flag. An uncertain parent should not necessarily discard a good role label. Nodes linked to unresolved/rejected proposals are excluded by default until reviewed. Retain valid root summaries as auxiliary screen-level supervision even though roots are not candidate element examples.

### 5.2 Splits

Group exact duplicates, near-duplicate views, related capture sessions, and before/after states before splitting. Many session IDs are null; reconstruct groups using capture provenance, visual similarity and manual inspection. Do not assume timestamps alone identify independent sessions.

Aim for approximately 70% train, 15% validation and 15% test **by groups**. Actual counts may differ. Where app coverage permits, maintain an additional held-out-app evaluation. Do not randomly split boxes or adjacent frames. Freeze split manifests and use test only after model/configuration selection.

Human-review the validation/test examples used for accuracy claims, plus a small training sample across apps. A practical initial review budget is 20–30 diverse screens, with fewer fully reviewed examples reported honestly if time runs out. If no reliable held-out set exists, report development results only.

### 5.3 OCR and contextual targets

Run OCR offline on original images and cache text, boxes, confidence, engine/version and timings. Manually correct a subset for OCR evaluation. OCR pseudo-labels are not ground truth. Our existing annotations cannot currently train exact text recognition.

Canonicalize a small contextual vocabulary from training data only, for example file_selection, navigation, search, document_content, tabular_content, code_content, terminal_output and loading_surface. Categories require review; do not assign terminal_error solely because a generic caption mentions the word error. Rare/unsupported categories become unknown or are merged under a documented parent category.

Encode reviewed or eligible descriptions/context with a pinned pretrained sentence encoder **offline**. Keep screen/parent context in the target when it adds meaning. A simple regression-to-embedding auxiliary objective avoids assuming that all other repeated buttons are contrastive negatives. If contrastive training is later added, handle equivalent captions as multiple positives.

### 5.4 Augmentation

Use mild scale changes, padding translations, modest brightness variation and proposal jitter. Transform every box/OCR coordinate consistently. Avoid horizontal flips, heavy blur, arbitrary text-changing transforms, and random crops that destroy parent context. Never manufacture new state labels by recoloring a control without checking the semantics.

## 6. GPU environment and data transfer

Known server: SSH alias `gpu3`, account `harshitj23`, NVIDIA A40 with about 46,068 MiB visible. Workspace: `/data/harshitj23/screen-understanding`. FortiClient VPN is required for access; server internet authentication is maintained separately. Do not store campus credentials in the dataset or training config.

Existing environment documented in `server/README.md`: `/data/harshitj23/envs/perception-py311`, with PyTorch 2.5.1+cu124 and Transformers 4.49.0 at the time of setup. Detector environment is separate. Treat those as recorded versions, not a fresh remote verification.

Read-only preflight, runnable now:

```bash
ssh gpu3 'nvidia-smi'
ssh gpu3 'df -h /data'
ssh gpu3 '/data/harshitj23/envs/perception-py311/bin/python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"'
```

Respect shared-server availability; do not terminate other users' processes. Create an isolated training environment rather than upgrading the working detector/Florence environments. Resolve compatible torch/torchvision/transformers/timm versions in that environment, smoke-test forward/backward and RoIAlign, then freeze dependencies and checkpoint revisions. Do not assume the ScreenVLM-specific PYTHONPATH overlay is appropriate for training.

Required packages by function: PyTorch, torchvision, Pillow, NumPy, transformers, safetensors, a sentence-embedding implementation, scipy for matching, jsonschema, and a configuration library. Use timm only if the selected backbone requires it. Verify licenses of the exact deployed checkpoints when selecting them for the startup.

The proposed exporter produces a self-contained `training/data/daily_01/` with relative paths. After it exists, transfer **only that export and training source**, excluding credentials:

```bash
# Proposed paths: run after implementing and validating the exporter.
rsync -av --progress screen_understanding/training/ gpu3:/data/harshitj23/screen-understanding/training/
```

No root workspace sync and no --delete are needed. Verify exported hashes after transfer. Put Hugging Face cache and run artifacts under /data. Keep model weights resident during latency tests; report model loading separately.

## 7. Training recipe

These are initial hyperparameters, not empirically optimized settings.

### Stage A: tensor and timing smoke test

Implement forward passes and losses; run one minibatch through backward. Check no NaNs, finite gradients, masking, padding, and source-coordinate round trips. Overfit 4–8 training screens to detect broken supervision; this is not evidence of generalization.

Before longer training, benchmark untrained heads on real proposal counts. This measures computational feasibility only. Separately run OCR end to end. Abort or resize the architecture if the non-generative path already exhausts the budget.

### Stage B: frozen-backbone adaptation

- Freeze the pretrained visual backbone; keep it in eval mode when caching features.
- Train feature adapters, context module, heads, and region queries.
- AdamW, initial learning rate 3e-4 for new parameters, weight decay 0.01.
- Batch two whole screens initially; accumulate four steps for effective batch eight.
- Mixed precision after verifying device support; gradient clipping at norm 1.0.
- Five percent warmup, cosine decay; evaluate after each epoch.
- Start with ten epochs, early-stop after three validation checks without improvement.

Cached visual features can accelerate this stage but must be keyed by backbone revision, image hash, resolution and transform. Disable augmentations incompatible with the cache. Preserve screen batches so relationships remain learnable; do not independently shuffle isolated crops.

### Stage C: selective backbone fine-tuning

Unfreeze the final visual blocks if B2/B3 improve over B1 but plateau. Initial rates: 1e-5 for pretrained parameters and 1e-4 for new modules. Start with five additional epochs and the same early-stopping rule. Recompute visual features; frozen-feature caches are no longer valid.

Reduce batch size if memory requires it rather than silently reducing input resolution. Log actual peak memory. Do not train the whole visual encoder aggressively on 163 distinct screenshots. Where affordable, repeat the selected configuration across three seeds.

### Loss definition

Initial weighted objective:

```text
L = 1.0 role_CE + 0.25 surface_CE + 0.5 content_CE
  + 0.5 reviewed_state_loss + 0.5 parent_CE
  + 0.25 proposal_validity_loss + 0.25 semantic_cosine_loss
  + 1.0 region_objectness_CE + 5.0 region_L1 + 2.0 region_GIoU
```

Normalize each term by its valid supervised examples, then aggregate per screen so dense screens do not dominate. Disable unsupported heads/losses when there are no reliable targets. State loss uses only reviewed applicable true/false targets; unknown is masked and emitted at inference when evidence is insufficient. Log each component and target count separately. Clip class weights rather than allowing a rare noisy class to dominate.

Fit confidence thresholds on validation data, reporting precision versus coverage. Softmax confidence is not automatically calibrated. Choose checkpoints by contextual correctness and coverage subject to latency, not minimum training loss.

## 8. Optional language experiment: bounded and separate

Benchmark pretrained SmolVLM-256M before modifying its architecture. Compare short captions for 1, 4, 16 and 50 regions, with 8/16/24 output-token caps. Supply local visual evidence and global context, and report image preprocessing/encoding cost rather than hiding it in precomputed inputs.

A naive crop-per-region VLM batch repeats visual encoding; label it as such. A future shared-feature decoder needs a region adapter and alignment training. It is not equivalent to changing batch_size in the stock model.

Fine-tune only after a feasible timing configuration exists: compact caption targets, pretrained decoder retained, adapters or selective fine-tuning, and reviewed held-out semantic scoring. Long Gemini prose should be compressed into factual targets with omitted detail recorded; a hard token cap can truncate meaningful content.

Keep enrichment task-independent for the perception experiment. Select regions by missing semantics or content complexity, not by a hidden action-planning objective. Emit `enrichment_pending`, `complete`, or `unavailable`. Report the fraction of regions enriched and time to fully enriched output. Never advertise an early partial graph as complete rich context in 500 ms.

## 9. Latency protocol and acceptance

Initial target envelope: one screenshot request at a time, resident model, documented input resolution, up to 128 candidate nodes, measured OCR workload. Also evaluate dense overflow screens. Final supported limits must follow measurements.

Record:

1. Capture and image encode/decode.
2. Mac-to-server transfer and queue wait.
3. Detector.
4. OCR detection and recognition.
5. Visual backbone.
6. ROI extraction, context module and heads.
7. Graph constraints and serialization.
8. Optional language generation.
9. Server wall time and client end-to-end wall time.

Use CUDA events for GPU components and synchronized monotonic wall timing for complete requests. Include CPU preprocessing, transfers and postprocessing. Benchmark without profiler overhead for reported numbers. Use at least 20 warmups and 200 measured requests across varied screens for an initial characterization; report sample count, p50, p95, p99, observed max and failures. Do not infer a guaranteed worst case from the observed maximum.

Start with sequential GPU stages. If overlapping stages is implemented, measure actual wall time under contention; do not replace measured time with the sum or maximum of isolated measurements. CPU/GPU OCR alternatives should be compared on the same screenshots and OCR accuracy.

The earlier approximately 1.7-second OCR stage is already a blocker. A role model cannot fix it. First measure alternative OCR settings/engines and bounded text-region processing; label any incomplete OCR coverage. Benchmark both fresh-screen and cached-update modes separately.

Acceptance proposal: p95 end-to-end below 500 ms within the declared envelope, with p99/max disclosed. This is weaker than the user's original worst-case target, so report it explicitly as an interim milestone. A strict service deadline needs admission control and explicit incomplete/error outcomes; it cannot guarantee complete perception for unbounded screens or arbitrary VPN delays.

## 10. Accuracy protocol

- Role macro-F1 and per-class results, including rare controls.
- State precision/recall with abstention coverage, especially selected and disabled appearance.
- Parent accuracy on eligible nodes and graph constraint repair frequency.
- Region recall/precision at IoU thresholds 0.5 and 0.75, separately from element detection.
- OCR character/word error rate on human-transcribed spans and missed-span recall.
- Context-category macro-F1 and confusion matrix.
- Human factuality and completeness review for descriptions, when generated.
- Coverage: useful content areas missed despite valid proposal dispositions.

Use fixed-context probes to test more than labels: distinguish tab selection, dialog versus application controls, table versus text content, blank/loading versus populated content, and disabled appearance. Separately record questions the structured graph cannot answer, such as explaining a novel error or chart trend. Those failures define the enrichment gap; do not conceal them with a role-only score.

Teacher agreement and human-reviewed accuracy are separate metrics. A screen with schema-valid output is not automatically understood correctly.

## 11. Implementation files to create

All entries below are proposed:

```text
screen_understanding/training/
  configs/structured_v0.yaml
  configs/caption_probe.yaml
  prepare_data.py          # portable export, masks, hashes, vocabulary
  review_splits.py         # duplicate/session groups and frozen splits
  cache_ocr.py             # OCR artifacts, provenance and timing
  cache_targets.py         # training-only description embeddings
  dataset.py              # whole-screen samples and coordinate transforms
  model.py                # encoder, ROI context, heads, region queries
  losses.py               # masking and matching
  train.py                # staged training and resumable checkpoints
  evaluate.py             # held-out quality, coverage and visual errors
  benchmark.py            # synchronized component and wall timings
  benchmark_caption.py    # separate short-generation experiment
  export_predictions.py   # versioned graph and reviewer output
  tests/                  # masks, transforms, splits, graph invariants
```

Proposed CLI contract, **not runnable until those modules exist**:

```bash
python prepare_data.py --inventory ../dataset/training_inventory/daily_01 --output data/daily_01
python review_splits.py --data data/daily_01 --output data/daily_01/splits.json
python cache_ocr.py --data data/daily_01 --config configs/structured_v0.yaml
python cache_targets.py --data data/daily_01 --split train
python benchmark.py --config configs/structured_v0.yaml --mode smoke --output runs/latency-smoke
python train.py --config configs/structured_v0.yaml --stage frozen --output runs/structured-v0
python train.py --config configs/structured_v0.yaml --stage finetune --resume runs/structured-v0/last.pt --output runs/structured-v0-ft
python evaluate.py --checkpoint runs/structured-v0-ft/best.pt --split test --output runs/structured-v0-ft/test
python benchmark.py --checkpoint runs/structured-v0-ft/best.pt --mode end-to-end --output runs/structured-v0-ft/latency
```

Run long jobs in tmux. Persist optimizer, scheduler, mixed-precision scaler where applicable, RNG states, split hash, config, data hashes and dependency versions. Resume only when those are compatible. Save predictions and visual error reports alongside metrics.

## 12. One-week execution order

| Day | Deliverable | Stop or revise when |
|---|---|---|
| 1 | Reviewed split, OCR timing, B0 and compute smoke tests | OCR/input processing already prevents the budget |
| 2 | Portable export, B1 training, transform/mask checks | Model cannot overfit the small debugging subset |
| 3 | B2 context and parent learning, region-head diagnostics | No gain over local role predictions |
| 4 | B3 semantic supervision and selective fine-tuning | Held-out behavior worsens or uncertainty is hidden |
| 5 | End-to-end region evaluation, optimized timing, G1 probe | Claimed speed depends on oracle boxes/cached images |
| 6 | Error corrections, selected configuration, limited delta experiment | Changes harm frozen validation metrics |
| 7 | Frozen demo, fresh-screen stress test, honest quality/latency report | Demo claims exceed measured coverage |

This is a scheduling target, not a runtime prediction. Prioritize a measured B2 result over unfinished custom caption machinery. No new annotation API campaign is necessary to begin this work; new labels should address observed gaps rather than volume alone.

## 13. Research basis

- [SmolVLM 256M/500M](https://huggingface.co/blog/smolervlm): pretrained small VLMs and their 93M visual encoder; foundation for optional generation and visual feature reuse.
- [Laya model card](https://huggingface.co/convaiinnovations/laya): text-only typed decisions and workload-dependent timings; useful architectural principle, not a screenshot latency benchmark.
- [Spotlight](https://arxiv.org/abs/2209.14927): region-focused UI understanding using screenshot context.
- [Tokenize Anything](https://arxiv.org/abs/2312.09128) and [Segment and Caption Anything](https://arxiv.org/abs/2312.00869): region semantic/caption modeling precedents; not proof of our latency target.
- [ConvNeXt V2](https://github.com/facebookresearch/ConvNeXt-V2): pretrained smaller visual-backbone alternative.
- [Torchvision RoIAlign](https://docs.pytorch.org/vision/stable/generated/torchvision.ops.roi_align.html): region sampling primitive; verify behavior against the installed torchvision version.

The proposed combination is an engineering design to test, not a claim of research novelty. Success means a contextual representation whose quality, coverage, and latency are demonstrated on held-out macOS screens.
