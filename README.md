# LLMOS — Multimodal Desktop Computer Use Agent (CUA) Ecosystem

[![Hugging Face Model](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Model-yellow)](https://huggingface.co/chhola14bhatoora/screen-understanding-micro-v2)
[![Hugging Face Dataset](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Dataset-blue)](https://huggingface.co/datasets/chhola14bhatoora/screen-understanding-captures)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)

An end-to-end open ecosystem for autonomous Computer Use Agents (CUAs) on desktop operating systems, combining specialized lightweight Vision-Language Models (VLMs), native macOS Accessibility Tree (AX) grounding, and deterministic agent execution runtimes.

---

## 🏛️ Ecosystem Overview

```
YC/ (llmos monorepo)
├── screen_understanding/       # VLM training, AX-vision mapping, inference server
├── LLM_OS/                     # Agent runtime, ATree tools, web interface & plans
├── arc-cua/                    # Autonomous CUA runtime with macOS AX & OCR backends
├── Ax_analysis/                # Empirical AX tree census & benchmarks across macOS apps
├── atree/ & atree_v2/          # Standalone accessibility tree inspection tools
├── lsfg/                       # Language-Screen Foundation Grounding logic & reasoning
└── vlm_testing/                # Multi-provider click & action evaluation harness
```

---

## 📦 Hosted Model Checkpoints & Datasets

To keep this codebase lightweight, fast to clone, and modular, all model weights and large multi-modal captures are hosted directly on Hugging Face:

| Asset | Description | Hugging Face Link |
| :--- | :--- | :--- |
| **Screen Understanding Micro V2** | Fine-tuned Idefics3/SmolVLM model specialized for desktop UI localization and element grounding (~489 MB) | [🤗 Model Hub](https://huggingface.co/chhola14bhatoora/screen-understanding-micro-v2) |
| **Desktop Captures & Traces Dataset** | 1,000+ annotated macOS application screenshots, bounding box groundings, and multi-step contextual runs | [🤗 Dataset Hub](https://huggingface.co/datasets/chhola14bhatoora/screen-understanding-captures) |

To download the model checkpoint via Python:
```python
from transformers import AutoProcessor, AutoModelForVision2Seq

processor = AutoProcessor.from_pretrained("chhola14bhatoora/screen-understanding-micro-v2")
model = AutoModelForVision2Seq.from_pretrained("chhola14bhatoora/screen-understanding-micro-v2")
```

---

## 🛠️ Modules Breakdown

### 1. [`screen_understanding/`](./screen_understanding)
Core perception engine for desktop automation:
- **`ax_mapping/`**: Hybrid coordinate grounding mapping raw vision clicks to macOS accessibility nodes.
- **`vision_only/`**: Pure visual perception baseline without reliance on accessibility trees.
- **`training/`**: Distributed training recipes, dataset preprocessing pipelines (`micro_v1`, `micro_v2_352`), and SafeTensors exporter.
- **`server/`**: High-throughput FastAPI inference server for realtime bounding box and action prediction.

### 2. [`LLM_OS/`](./LLM_OS)
The higher-level agent environment and desktop orchestration framework:
- **`llm_os/`**: System runtime and process management.
- **`ATree_tool/`**: Accessibility Tree extraction and interaction tools for agents.
- **`Product_web/`**: Modern interactive UI and design assets.
- **`plans/` & `Lit Review/`**: Architectural research and design roadmaps.
- **`testing/openclaw_probes/`**: Custom CUA probes and interaction token tests.

### 3. [`arc-cua/`](./arc-cua)
Autonomous computer use agent with type-safe execution:
- Native backends for `macos_ax.py`, `macos_ocr.py`, and `macos_hybrid.py`.
- Type-safe agent policies and execution loop protocols.

### 4. [`Ax_analysis/`](./Ax_analysis)
Extensive accessibility tree census across macOS desktop software:
- Empirical captures and node coverage analysis for Brave Browser, Claude Desktop, Canva, Apple Calendar, and Antigravity IDE.

### 5. [`lsfg/`](./lsfg)
Language-Screen Foundation Grounding implementation, reasoning specifications, and benchmark test suites.

### 6. [`vlm_testing/`](./vlm_testing)
Evaluation suite comparing coordinate prediction accuracy across various VLM APIs (Groq, Lightcone, PTA-1).

---

## 🚀 Quickstart

### Prerequisites
- macOS Sonoma / Sequoia (recommended for native AX APIs)
- Python 3.11+
- Node.js 20+

### Setup
```bash
# Clone the repository
git clone https://github.com/chhola14bhatoora/llmos.git
cd llmos

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies for screen understanding
pip install -r screen_understanding/requirements.txt # or install module-specific requirements
```

---

## 📄 License
This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.
