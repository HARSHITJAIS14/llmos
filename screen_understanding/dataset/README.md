---
tags:
- screen-understanding
- computer-use-agent
- cua
- desktop-automation
- multimodal
- gui-grounding
license: apache-2.0
task_categories:
- visual-question-answering
- object-detection
---

# Screen Understanding Captures Dataset

This dataset contains real-world macOS desktop UI interaction traces, accessibility tree snapshots, bounding box groundings, and contextual multi-step agent runs for training and evaluating Computer Use Agents (CUAs).

## Structure
- `captures_1000/`: High-resolution UI screenshots annotated with UI bounding boxes and semantic element labels.
- `contextual_lite_runs/`: Multi-step sequential desktop runs recorded across productivity apps.
- `pilot_v001/`: Pilot validation set for initial schema verification.
- `training_inventory/`: Data indexes and splits.

## Associated Repositories
- **GitHub Monorepo**: [llmos](https://github.com/HARSHITJAIS14/llmos)
- **Model Checkpoint**: [screen-understanding-micro-v2](https://huggingface.co/chhola14bhatoora/screen-understanding-micro-v2)
- **Hugging Face Dataset**: [screen-understanding-captures](https://huggingface.co/datasets/chhola14bhatoora/screen-understanding-captures)

## Downloading the Dataset Locally
The raw captures and contextual runs (~4 GB) are hosted on Hugging Face to keep the repository lightweight. To download the dataset locally:
```bash
hf download chhola14bhatoora/screen-understanding-captures --repo-type dataset --local-dir screen_understanding/dataset
```

