"""Launcher for full daily contextual annotation run across all interleaved screens."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path("/Users/harshit/Desktop/YC")
QUEUE_FILE = REPO_ROOT / "screen_understanding/dataset/scratch/daily_screens_queue.json"
OUTPUT_DIR = REPO_ROOT / "screen_understanding/dataset/contextual_lite_runs/full_daily_run"
PYTHON_BIN = "/Users/harshit/miniconda3/bin/python"
SCRIPT = REPO_ROOT / "screen_understanding/dataset/scripts/run_contextual_lite.py"


def main():
    with open(QUEUE_FILE) as f:
        screens = json.load(f)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"=======================================================")
    print(f"STARTING FULL DAILY CONTEXTUAL LITE RUN (DAY 2)")
    print(f"Target Queue: {len(screens)} interleaved screens across 21 applications")
    print(f"Output Directory: {OUTPUT_DIR}")
    print(f"Budget: 950 max calls (480 allowance per model)")
    print(f"Models: gemini-3.5-flash-lite & gemini-3.1-flash-lite")
    print(f"Rate Limiter: 12 RPM per model (24 RPM total)")
    print(f"Workers: 2 concurrent API threads")
    print(f"Constraints: Strictly <5 token descriptions/names for micro-captioning")
    print(f"=======================================================\n")

    cmd = [
        PYTHON_BIN,
        str(SCRIPT),
        "--output", str(OUTPUT_DIR),
        "--workers", "2",
        "--chunk-size", "20",
        "--rpm", "12",
        "--daily-budget", "480",
        "--max-calls", "950",
        "--models", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
        "--screens", *screens
    ]

    subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
