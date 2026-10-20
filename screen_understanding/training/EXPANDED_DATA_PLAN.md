# Expanded-data continuation: 352 annotated screens

2026-10-19. Continue from `micro-train-v2/best`; preserve that checkpoint and evaluation as the comparison baseline. Do not overwrite old results or train a new model from scratch.

## Verified input

Inventory `dataset/training_inventory/expanded_352`: 352 annotation files, 300 distinct decoded-pixel images, 23,408 total nodes, 21,124 structurally eligible non-root nodes before duplicate removal. All input hashes, geometry and schema checks passed. Labels remain teacher-generated, with no human-reviewed records. No annotation API calls are needed.

Exporter removes duplicate images across the whole campaign. Keep Preview as validation and System Settings as test, preserving the original application split. There are no additional app categories in the expanded batch. Record previously seen pixel hashes so evaluation can distinguish old regression screens from newly added held-out screens. New images in the same app are not guaranteed novel layouts; inspect similarity before generalization claims.

Prepared export after preserving historical pixel-group assignments: 252 training screens / 15,649 candidate boxes, 8 validation screens / 526 boxes, and 40 test screens / 2,307 boxes, before five-token filtering. Newly added distinct captures comprise 110 train, 2 validation and 25 test screens. Use `--previous-export training/data/micro_v1` when regenerating this export; a duplicate capture under a different app name must not change a historical split.

Local tokenizer preflight retained 14,594 train targets, 501 validation targets, and 2,174 test targets. 1,213 targets exceed the accepted five-token contract and are excluded. The split and overview-dropout invariants were tested locally. After VPN reconnection, all 300 transferred images passed remote pixel-hash verification and record-to-screen split checks. The launcher is active in tmux `micro-expanded-v1`; smoke testing precedes main training. The existing monitoring automation is active for the expanded job.

## Training contract

- Same SmolVLM-256M checkpoint family and frozen visual encoder.
- Same five-token limit, semantic-name filtering and 512x512 overview/target composite.
- Start from the previous best weights, with a new optimizer for the expanded dataset; this is weight initialization, not resume of the old dataset's sampler.
- AdamW learning rate 1e-5, two epochs, physical batch 16, accumulation 1.
- For 25% of training samples, replace the overview half with its neutral background while retaining the target crop. At validation/inference retain the full composite. This regularization tests dependence on global context; do not claim its benefit until comparison results exist.
- Cached uint8 composites, numeric preprocessing equivalence checks, all-target token-boundary validation, checkpoints every 25 optimizer steps with atomic completion markers.
- Run the two-step smoke test before the main run. It starts from the same baseline as main training; smoke weights are not reused.

The incoming data contains many more boxes and layouts but is still limited to 22 app buckets. More data alone cannot ensure local grounding. Track unrelated uses of Appearance and Window Icon, target-specific descriptions, cap hits, and performance separately for controls versus regions. Do not blacklist legitimate labels or score every synonym as an error.

## Evaluation

Compare old and new checkpoints on exactly the same held-out inputs, then report fresh held-out screens separately. The first fixed validation subset is used for model selection, so do not call it a blind test. Preserve test records untouched by fitting and checkpoint selection.

Measure complete 1/8/32/50-box requests including preprocessing, visual encoding and generation. Report cold and warm timing, batch size, and exclusions. Neither a five-token cap nor averaged per-box throughput proves 500 ms full-screen perception.

## Files and job

- Export: `training/data/micro_v2_352`.
- Smoke output: `training/runs/micro-expanded-smoke-v1`.
- Main output: `training/runs/micro-train-v3`.
- Launcher: `training/launch_expanded.sh`.
- Persistent tmux session: `micro-expanded-v1`.
- Log: `training/runs/expanded-campaign.log`.
- Status: `training/runs/expanded-campaign-status.json`.

Remote root is `/data/harshitj23/screen-understanding`. The launcher records immediate job exit status; the chat monitoring automation should inspect status/logs/checkpoints and report meaningful failures or completion. Do not run multiple GPU training jobs simultaneously.
