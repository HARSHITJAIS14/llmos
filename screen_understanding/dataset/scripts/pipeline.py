"""End-to-end pipeline coordinator for contextual screen-perception pilot dataset."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from typing import Dict, List, Optional
from PIL import Image

from crop_transform import CropTransform, clip_box, validate_box
from detector import detect_proposals
from gemini_teacher import GeminiTeacher
from stage_c_global import run_stage_c
from stage_d_region import annotate_region
from stage_e_audit import run_stage_e
from stage_f_pair import run_stage_f_pair
from validate import validate_annotation_file
from render_review import generate_review_artifact

REPO_ROOT = Path(__file__).resolve().parents[3]


def process_screen(
    screen_id: str,
    source_png: Path,
    screen_output_dir: Path,
    teacher: GeminiTeacher,
    use_remote_detector: bool = True,
) -> Dict:
    """Run full pipeline for a single screen."""
    screen_output_dir.mkdir(parents=True, exist_ok=True)
    source_target = screen_output_dir / "source.png"
    if not source_target.exists():
        shutil.copy2(source_png, source_target)

    im = Image.open(source_target).convert("RGB")
    w, h = im.size
    sha256 = hashlib.sha256(source_target.read_bytes()).hexdigest()

    # 1. Source metadata
    meta = {
        "screen_id": screen_id,
        "source_path": str(source_png),
        "sha256": sha256,
        "width": w,
        "height": h,
        "timestamp": time.time(),
    }
    (screen_output_dir / "source_metadata.json").write_text(json.dumps(meta, indent=2))

    # 2. Stage B: Detector proposals
    proposals_dir = screen_output_dir / "proposals"
    raw_json = proposals_dir / "raw.json"
    if raw_json.exists():
        proposals_data = json.loads(raw_json.read_text())
    else:
        proposals_data = detect_proposals(source_target, proposals_dir, use_remote=use_remote_detector)

    # 3. Stage C: Global Area Discovery
    teacher_ann_file = screen_output_dir / "annotation.teacher.json"
    reviewed_ann_file = screen_output_dir / "annotation.reviewed.json"

    if teacher_ann_file.exists():
        full_ann = json.loads(teacher_ann_file.read_text())
    else:
        stage_c_res = run_stage_c(screen_id, source_target, proposals_data, screen_output_dir, teacher)
        discovered_nodes = stage_c_res["nodes"]
        screen_context = stage_c_res["screen_context"]

        # 4. Stage D: Contextual Annotation in each region
        all_nodes = list(discovered_nodes)
        all_dispositions = {}
        curr_idx = 100

        # Discover major regions (level == "region" or "window")
        major_regions = [n for n in discovered_nodes if n["level"] in ["region", "window"]]

        for reg in major_regions:
            child_nodes, reg_disps, next_idx = annotate_region(
                region_node=reg,
                source_im=im,
                all_proposals=proposals_data.get("proposals", []),
                output_dir=screen_output_dir,
                teacher=teacher,
                start_node_index=curr_idx,
            )
            all_nodes.extend(child_nodes)
            all_dispositions.update(reg_disps)
            curr_idx = next_idx

        # Account for all remaining proposals
        for p in proposals_data.get("proposals", []):
            pid = p["id"]
            if pid not in all_dispositions:
                all_dispositions[pid] = {
                    "disposition": "unresolved",
                    "node_ids": [],
                    "reason": "Not mapped during regional annotation",
                }

        # Assemble full initial teacher annotation
        full_ann = {
            "schema_version": "0.1.0",
            "screen_id": screen_id,
            "image": {
                "path": "source.png",
                "sha256": sha256,
                "width": w,
                "height": h,
                "scale_factor": 2.0,
                "coordinate_space": "source_pixels_xyxy",
            },
            "screen_context": screen_context,
            "nodes": all_nodes,
            "relations": [],
            "coverage": {
                "status": "complete",
                "uninspected_regions": [],
                "unresolved_proposal_ids": [pid for pid, d in all_dispositions.items() if d["disposition"] == "unresolved"],
                "proposals_disposition": all_dispositions,
            },
            "annotation_provenance": {
                "model_requested": "gemini-3.8-flash",
                "model_returned": "gemini-3.8-flash",
                "thinking_requested": "high",
                "prompt_version": "0.1.0",
                "human_reviewed": False,
                "audit_applied": False,
            },
        }
        teacher_ann_file.write_text(json.dumps(full_ann, indent=2) + "\n")

    # 5. Stage E: Audit & Patches
    if not reviewed_ann_file.exists():
        patched_nodes, audit_raw = run_stage_e(full_ann["nodes"], im, screen_output_dir, teacher)
        reviewed_ann = dict(full_ann)
        reviewed_ann["nodes"] = patched_nodes
        reviewed_ann["annotation_provenance"]["audit_applied"] = True
        reviewed_ann["annotation_provenance"]["audit_version"] = "0.1.0"
        reviewed_ann_file.write_text(json.dumps(reviewed_ann, indent=2) + "\n")
    else:
        reviewed_ann = json.loads(reviewed_ann_file.read_text())

    # 6. Validation
    val_report = validate_annotation_file(
        annotation_path=reviewed_ann_file,
        image_path=source_target,
        raw_proposals_path=proposals_dir / "raw.json",
    )

    return {
        "screen_id": screen_id,
        "node_count": len(reviewed_ann["nodes"]),
        "valid": val_report["valid"],
        "validation_report": val_report,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-dir", type=Path, default=REPO_ROOT / "screen_understanding/dataset/pilot_v001")
    parser.add_argument("--screens", nargs="*", help="Specific screen IDs to run")
    parser.add_argument("--local-detector", action="store_true")
    args = parser.parse_args()

    pilot_dir = args.pilot_dir
    pilot_dir.mkdir(parents=True, exist_ok=True)

    teacher = GeminiTeacher()

    screens_dir = pilot_dir / "screens"
    if not screens_dir.exists():
        print(f"Screens directory does not exist at {screens_dir}")
        return

    screen_folders = sorted(screens_dir.glob("*"))
    if args.screens:
        screen_folders = [s for s in screen_folders if s.name in args.screens]

    print(f"Processing {len(screen_folders)} screens...")
    for s_path in screen_folders:
        sid = s_path.name
        src_png = s_path / "source.png"
        if not src_png.exists():
            continue
        print(f"\n--- Processing Screen {sid} ---")
        res = process_screen(
            screen_id=sid,
            source_png=src_png,
            screen_output_dir=s_path,
            teacher=teacher,
            use_remote_detector=not args.local_detector,
        )
        print(f"Result for {sid}: {res['node_count']} nodes, Valid: {res['valid']}")

    # Regenerate review artifact
    generate_review_artifact(pilot_dir)


if __name__ == "__main__":
    main()
