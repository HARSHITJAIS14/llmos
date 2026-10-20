#!/usr/bin/env bash
set -euo pipefail
cd /data/harshitj23/screen-understanding/training
export HF_HOME=/data/harshitj23/cache/huggingface
export CUDA_VISIBLE_DEVICES=0
export TOKENIZERS_PARALLELISM=false
export PYTHONPATH=/data/harshitj23/screen-understanding/libs/screenvlm-transformers
PYTHON=/data/harshitj23/envs/perception-py311/bin/python
mkdir -p runs
"$PYTHON" -u train_micro.py --data data/micro_v1 --output runs/micro-smoke-v3 --max-steps 2
"$PYTHON" -u train_micro.py --data data/micro_v1 --output runs/micro-train-v2 --epochs 2
