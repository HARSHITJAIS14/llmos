# One-day experiment: five-token contextual box labels

## Scope

Fine-tune SmolVLM-256M using existing teacher-labeled screenshots. Return a short contextual name for each box; the later harness receives the full screenshot as well. Examples: “Appearance settings”, “Search field”, “File selection”, “Terminal output”. This is micro-captioning, not exhaustive perception or action planning.

Maximum output is **five model tokenizer tokens**, excluding special tokens. Five tokens are not necessarily five words. The cap can truncate an inference response; report cap-hit rate rather than assuming every output finishes naturally. Do not promise 500 ms until a complete multi-box batch is measured.

## Implementation selected for today

- Pretrained `HuggingFaceTB/SmolVLM-256M-Instruct`.
- Freeze visual encoder; train connector and language model with supervised cross entropy.
- Each example is one 512x512 composite: screen overview with target outlined in red on the left; enlarged target with surrounding margin on the right.
- Disable automatic image splitting. This bounds the number of visual inputs.
- Prompt asks for a short contextual label. It supplies no app name or teacher role.
- Retain context in visual input; train on both region and element boxes.
- Use semantic_name from the teacher as the short target. Accept an original name if it fits five tokens. Otherwise remove a small set of generic UI suffix phrases and accept only if it fits. Exclude names still over budget; never arbitrarily cut targets mid-phrase.
- Preserve descriptions and context in the export for inspection, but they are not currently decoder targets. The short names are imperfect teacher supervision, not human ground truth.

This simple crop/overview baseline repeats image encoding per box. It is deliberately quick to implement and is **not the proposed shared-image-feature architecture**. Its full-screen latency may fail. Training establishes whether short contextual labels are useful before spending the harness time on custom inference machinery.

## Data and split

`prepare_micro.py` exports only structurally eligible non-root nodes from the existing inventory. Exact duplicate screenshots are removed using decoded-pixel hashes. The export has portable paths and no API credentials.

Hold out Preview for validation and System Settings for final test; train on other apps. Entire apps remain in one split, keeping repeated views from the same app together. Embedded content across apps can still be related; this split is a first conservative development experiment, not a large benchmark.

No test data is used for training, target vocabulary construction, validation loss selection or baseline tuning. Token-budget filtering is deterministic and applied equally to all splits. Report excluded targets and resulting app/role coverage. Do not infer reliable long-tail accuracy from this small dataset.

## Training configuration

- A40, bfloat16, SDPA; existing isolated perception-py311 environment with the existing Transformers 4.55.2 overlay at `/data/harshitj23/screen-understanding/libs/screenvlm-transformers`. The installed 4.49.0 does not support SDPA for this vision encoder; the first smoke attempt caught this before training.
- Batch 8, accumulation 2; AdamW learning rate 2e-5, weight decay 0.01.
- Frozen visual encoder, gradient clipping 1.0.
- First run: **two optimizer steps**, including baseline prediction, forward/backward and checkpoint validation.
- Main run: two epochs, validation after each epoch; no automatic additional epochs.
- Only target and EOS tokens contribute to loss; prompt/image/padding labels are masked.
- Verify prompt-token prefix equality to avoid off-by-one target masking.
- Save baseline/epoch predictions on the same 24 validation examples; validation loss on a fixed 128-example subset.
- Save last/best model, processor, optimizer state, seed, model revision, config, targets and per-step timing/memory logs.

Training loss and teacher-label agreement do not establish visual correctness. Inspect predictions against screenshots. If short targets are too generic or high-confidence mistakes persist, fix examples instead of extending training blindly.

## Execution

From the Mac:

```bash
/Users/harshit/miniconda3/bin/python screen_understanding/training/prepare_micro.py \
  --output screen_understanding/training/data/micro_v1
rsync -av --progress screen_understanding/training/ \
  gpu3:/data/harshitj23/screen-understanding/training/
```

On gpu3, from `/data/harshitj23/screen-understanding/training`:

```bash
export PYTHONPATH=/data/harshitj23/screen-understanding/libs/screenvlm-transformers
HF_HOME=/data/harshitj23/cache/huggingface CUDA_VISIBLE_DEVICES=0 \
 /data/harshitj23/envs/perception-py311/bin/python -u train_micro.py \
 --data data/micro_v1 --output runs/micro-smoke-v2 --max-steps 2

# Only after the smoke test passes; run in a detached tmux session.
HF_HOME=/data/harshitj23/cache/huggingface CUDA_VISIBLE_DEVICES=0 \
 /data/harshitj23/envs/perception-py311/bin/python -u train_micro.py \
 --data data/micro_v1 --output runs/micro-train-v1 --epochs 2
```

Output directories must be new. Training state is saved for recovery, but this first script does not yet implement resume loading. Do not claim it is resumable until that path is implemented and tested.

## Timing and handoff

After training, benchmark 1/8/32/50 boxes in batches using max_new_tokens=5, and include composite construction, preprocessing, transfer to GPU, encoding and decoding. Report single-box versus whole-screen timing separately. Measure detector and network cost separately, then include them in end-to-end results. An image-generation cap is not a latency guarantee.

If 50-box inference exceeds budget, keep the trained model as an optional enrichment component and report the measured limit; do not secretly reduce coverage. Potential next optimizations are caching unchanged boxes, reducing redundant proposals, and shared visual features. Those are follow-up work, not assumed speedups in this experiment.

Handoff artifacts: checkpoint path and revision, inference prompt/preprocessing contract, per-box input/output API, held-out predictions with screenshots, measured batch latency, token cap/truncation behavior, and known semantic errors. The harness should consume box ID, source-pixel bbox, short label and provenance, together with the original screen.

## Time allocation

First 2 hours: export, smoke test and training launch. Next block: finish the bounded two-epoch run and inspect held-out results. Remaining perception time: benchmark and package a minimal inference interface. Stop expanding architecture scope; the next project stage is harness and agents.
