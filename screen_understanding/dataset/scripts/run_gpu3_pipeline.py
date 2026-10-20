"""Pipeline to batch-sync images to gpu3, run OmniParser detection on NVIDIA A40, and pull back proposals."""
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Dict, List

LOCAL_SCREENS = Path("/Users/harshit/Desktop/YC/screen_understanding/dataset/captures_1000/screens")
LOCAL_PROPOSALS = Path("/Users/harshit/Desktop/YC/screen_understanding/dataset/captures_1000/proposals")
LOCAL_MANIFEST = Path("/Users/harshit/Desktop/YC/screen_understanding/dataset/captures_1000/manifest.jsonl")
REMOTE_SCREENS = "/data/harshitj23/screen-understanding/runs/captures_1000/screens"
REMOTE_PROPOSALS = "/data/harshitj23/screen-understanding/runs/captures_1000/proposals"


def run_pipeline(chunk_size: int = 50):
    LOCAL_PROPOSALS.mkdir(parents=True, exist_ok=True)
    all_local_pngs = sorted(glob.glob(str(LOCAL_SCREENS / "*.png")))
    total_screens = len(all_local_pngs)
    print(f"Total local screens to process: {total_screens}")

    t_start_pipeline = time.time()

    # Process in chunks of screens: transfer chunk -> detect chunk -> pull proposals
    for chunk_idx, i in enumerate(range(0, total_screens, chunk_size), start=1):
        chunk_files = all_local_pngs[i:i + chunk_size]
        chunk_names = [Path(p).name for p in chunk_files]
        first_id = Path(chunk_files[0]).stem
        last_id = Path(chunk_files[-1]).stem

        # Check if already processed locally
        unprocessed = [
            f for f in chunk_files
            if not (LOCAL_PROPOSALS / f"{Path(f).stem}.json").exists()
        ]
        if not unprocessed:
            print(f"Chunk {chunk_idx} ({first_id}..{last_id}) already complete. Skipping.")
            continue

        print(f"\n--- Processing Chunk {chunk_idx}: {first_id} to {last_id} ({len(chunk_files)} screens) ---")

        # 1. Transfer chunk to gpu3
        t_sync0 = time.time()
        file_list_str = " ".join(str(p) for p in chunk_files)
        rsync_cmd = f"rsync -av {file_list_str} gpu3:{REMOTE_SCREENS}/"
        subprocess.run(rsync_cmd, shell=True, check=True, stdout=subprocess.DEVNULL)
        t_sync = time.time() - t_sync0
        print(f"  Synced {len(chunk_files)} screens to gpu3 in {t_sync:.1f}s.")

        # 2. Run batch detection on gpu3
        t_det0 = time.time()
        remote_cmd = (
            "source /data/harshitj23/miniforge3/etc/profile.d/conda.sh && "
            "conda activate /data/harshitj23/envs/perception-py311 && "
            "python /data/harshitj23/screen-understanding/run_batch_detector.py --batch-size 16"
        )
        res = subprocess.run(["ssh", "gpu3", remote_cmd], capture_output=True, text=True, check=True)
        t_det = time.time() - t_det0
        print(f"  GPU detection completed in {t_det:.1f}s.")

        # 3. Pull back proposals for this chunk
        t_pull0 = time.time()
        pull_cmd = f"rsync -av gpu3:{REMOTE_PROPOSALS}/ {LOCAL_PROPOSALS}/"
        subprocess.run(pull_cmd, shell=True, check=True, stdout=subprocess.DEVNULL)
        t_pull = time.time() - t_pull0

        # Count completed proposals
        completed_count = len(list(LOCAL_PROPOSALS.glob("screen_*.json")))
        elapsed = time.time() - t_start_pipeline
        print(f"  Proposals pulled in {t_pull:.1f}s. Total done so far: [{completed_count}/{total_screens}] in {elapsed:.1f}s")

    elapsed_all = time.time() - t_start_pipeline
    completed_all = len(list(LOCAL_PROPOSALS.glob("screen_*.json")))
    print(f"\n=======================================================")
    print(f"ALL CHUNKS COMPLETE! {completed_all}/{total_screens} processed in {elapsed_all:.1f}s.")
    print(f"=======================================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk-size", type=int, default=50)
    args = parser.parse_args()
    run_pipeline(chunk_size=args.chunk_size)
