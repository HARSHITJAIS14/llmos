#!/usr/bin/env bash
set -euo pipefail
cd /data/harshitj23/screen-understanding/training
export HF_HOME=/data/harshitj23/cache/huggingface
export CUDA_VISIBLE_DEVICES=0
export TOKENIZERS_PARALLELISM=false
export PYTHONPATH=/data/harshitj23/screen-understanding/libs/screenvlm-transformers
PYTHON=/data/harshitj23/envs/perception-py311/bin/python
mkdir -p runs
status=runs/expanded-campaign-status.json
trap 'rc=$?; if [ "$rc" -ne 0 ]; then printf "{\"status\":\"failed\",\"exit_code\":%s}\n" "$rc" > "$status"; fi' EXIT
printf '{"status":"smoke_test"}\n' > "$status"
"$PYTHON" -u train_micro.py --data data/micro_v2_352 --output runs/micro-expanded-smoke-v1 \
  --init-checkpoint runs/micro-train-v2/best --epochs 2 --lr 1e-5 \
  --overview-dropout .25 --max-steps 2 --skip-baseline-predictions
printf '{"status":"training"}\n' > "$status"
"$PYTHON" -u train_micro.py --data data/micro_v2_352 --output runs/micro-train-v3 \
  --init-checkpoint runs/micro-train-v2/best --epochs 2 --lr 1e-5 --overview-dropout .25
printf '{"status":"completed"}\n' > "$status"
