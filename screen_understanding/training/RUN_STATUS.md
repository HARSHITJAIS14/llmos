# Micro-caption training status

**Latest update, 2026-10-19:** expanded continuation `micro-train-v3` completed both epochs (1,826 steps). Old/new checkpoint comparison and 1/8/32/50-box latency measurements are complete. See [results](runs/micro-train-v3/comparison-v2/RESULTS.md) and [comparison gallery](runs/micro-train-v3/comparison-v2/index.html). Earlier notes below describe the original training attempt and are historical.

Updated 2026-10-18. This file is a point-in-time record, not a live monitor.

**Smoke test passed:** two optimizer steps, finite gradients, validation and checkpoint saves completed (`micro-smoke-v3`). Baseline validation loss 8.3603; after two steps 7.9892. Peak allocated GPU memory approximately 2,818 MiB.

**Main run completed (micro-train-v2):** all 780 optimizer steps across 2 epochs finished successfully in 274 seconds (~4.5 minutes) on the NVIDIA A40. Validation loss converged from baseline 8.3603 down to **3.9699** (best val loss). Atomic checkpoints saved every 25 steps; final model and processor exported to `runs/micro-train-v2/best` and `runs/micro-train-v2/last`.

## Prepared and verified

- 163 exact-unique screenshots exported and transferred to gpu3; all decoded-pixel hashes verified remotely.
- Training: 142 screens, 6,226 eligible targets of at most five tokenizer tokens.
- Validation: 6 Preview screens, 373 targets; fixed 128-target subset for development loss.
- Test: 15 System Settings screens, 747 targets; not used for fitting.
- 982 long targets excluded across splits. 7,296 names retained verbatim, 50 accepted after removing generic suffix wording.
- Teacher labels remain unreviewed. These are development data, not audited ground truth.

## Runtime

- GPU: NVIDIA A40, initially idle.
- Python: `/data/harshitj23/envs/perception-py311/bin/python`.
- PyTorch: 2.5.1+cu124.
- Transformers overlay: 4.55.2 at `/data/harshitj23/screen-understanding/libs/screenvlm-transformers`.
- Model: `HuggingFaceTB/SmolVLM-256M-Instruct`, revision `7e3e67edbbed1bf9888184d9df282b700a323964`.
- Actual frozen parameter count: 86,433,024; actual trainable count: 170,051,904.

## Job locations

Server working directory: `/data/harshitj23/screen-understanding/training`.

- tmux session: `micro-caption-v1`.
- Campaign log: `runs/campaign-v2.log`.
- Smoke run: `runs/micro-smoke-v2`.
- Main two-epoch run: `runs/micro-train-v1` (launches only after smoke succeeds).

The first attempt (`micro-smoke-v1`, `campaign-v1.log`) failed during model loading because Transformers 4.49.0 did not support the requested SDPA vision implementation. No optimizer steps occurred in that attempt. The existing 4.55.2 overlay resolves that compatibility issue without changing installed environments.

Inspect the campaign with:

```bash
ssh gpu3 'tail -n 20 /data/harshitj23/screen-understanding/training/runs/campaign-v2.log'
```

See ONE_DAY_PLAN.md for the input contract, limits, and evaluation plan. A five-token cap does not establish 500 ms latency; neither the training run nor its single-box diagnostic timings certify whole-screen performance.
