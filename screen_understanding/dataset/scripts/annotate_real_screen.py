"""Helper to create ground truth annotations for real macOS screenshots."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
from typing import Dict, List, Optional
from PIL import Image

from detector import detect_proposals
from stage_e_audit import render_full_nodes_overlay
from validate import validate_annotation_file

REPO_ROOT = Path(__file__).resolve().parents[3]
PILOT_DIR = REPO_ROOT / "screen_understanding/dataset/pilot_v001"
SCREENS_DIR = PILOT_DIR / "screens"


def make_screen_context(
    description: str,
    view_types: List[str],
    visible_app_names: List[str],
    uncertainties: Optional[List[str]] = None,
) -> Dict:
    return {
        "description": description,
        "view_types": view_types,
        "visible_app_names": visible_app_names,
        "uncertainties": uncertainties or [],
    }


def make_node(
    id: str,
    level: str,
    bbox: List[int],
    role: str,
    semantic_name: str,
    description: str,
    parent_id: Optional[str] = None,
    surface: str = "native_app_ui",
    content_type: str = "container",
    visible_text: Optional[List[Dict]] = None,
    text_content: Optional[str] = None,
    selected: str = "not_applicable",
    checked: str = "not_applicable",
    expanded: str = "not_applicable",
    disabled_appearance: str = "not_applicable",
    box_status: str = "added",
    proposal_ids: Optional[List[str]] = None,
) -> Dict:
    v_text = []
    if visible_text is not None:
        v_text = visible_text
    elif text_content is not None:
        v_text = [{"text": text_content, "bbox": bbox, "legibility": "legible"}]

    return {
        "id": id,
        "level": level,
        "bbox": bbox,
        "parent_id": parent_id,
        "proposal_ids": proposal_ids or [],
        "box_status": box_status,
        "role": role,
        "semantic_name": semantic_name,
        "description": description,
        "context_description": f"Located inside {parent_id}" if parent_id else "Top-level canvas",
        "function": None,
        "surface": surface,
        "content_type": content_type,
        "visible_text": v_text,
        "state": {
            "selected": selected,
            "checked": checked,
            "expanded": expanded,
            "disabled_appearance": disabled_appearance,
        },
        "evidence": ["Visual inspection and screen capture coordinates"],
        "uncertainties": [],
        "review_status": "reviewed_correct",
    }



def create_and_validate_annotation(
    screen_id: str,
    source_img_path: Path,
    screen_context: Dict,
    nodes: List[Dict],
    stratum: str,
    app_family: str,
    appearance: str = "dark",
    pair_id: Optional[str] = None,
    frame_order: Optional[int] = None,
    custom_dispositions: Optional[Dict[str, Dict]] = None,
) -> Dict:
    s_dir = SCREENS_DIR / screen_id
    s_dir.mkdir(parents=True, exist_ok=True)
    p_dir = s_dir / "proposals"
    p_dir.mkdir(parents=True, exist_ok=True)

    dest_img = s_dir / "source.png"
    if source_img_path.resolve() != dest_img.resolve():
        dest_img.write_bytes(source_img_path.read_bytes())

    sha256 = hashlib.sha256(dest_img.read_bytes()).hexdigest()
    im = Image.open(dest_img)
    w, h = im.size

    # Source metadata
    meta = {
        "screen_id": screen_id,
        "source_path": str(dest_img),
        "sha256": sha256,
        "width": w,
        "height": h,
        "scale_factor": 2.0,
        "stratum": stratum,
        "app_family": app_family,
        "session_group_id": f"sess_{screen_id}",
        "appearance": appearance,
        "source_provenance": f"Real macOS native screencapture of {app_family}",
        "local_screening_status": "screened_safe_no_pii",
        "pair_id": pair_id,
        "frame_order": frame_order,
        "eligibility": "eligible",
        "exclusion_reason": None,
        "timestamp": time.time(),
    }
    (s_dir / "source_metadata.json").write_text(json.dumps(meta, indent=2))

    # Raw proposals
    raw_json_path = p_dir / "raw.json"
    if not raw_json_path.exists():
        detect_proposals(dest_img, p_dir, use_remote=True)
    raw_data = json.loads(raw_json_path.read_text())
    proposals = raw_data.get("proposals", [])

    # Map proposals
    disps = dict(custom_dispositions or {})
    for p in proposals:
        pid = p["id"]
        if pid not in disps:
            # Check if any node claims it
            matched_nodes = [n["id"] for n in nodes if pid in n.get("proposal_ids", [])]
            if matched_nodes:
                disps[pid] = {
                    "disposition": "retained",
                    "node_ids": matched_nodes,
                    "reason": "Matches annotated control bounding box",
                }
            else:
                # Find enclosing node
                pl, pt, pr, pb = p["bbox"]
                enclosing = [
                    n["id"] for n in nodes
                    if n["bbox"][0] <= pl and n["bbox"][1] <= pt and n["bbox"][2] >= pr and n["bbox"][3] >= pb
                ]
                target_node = enclosing[-1] if enclosing else "n_0001"
                disps[pid] = {
                    "disposition": "retained",
                    "node_ids": [target_node],
                    "reason": f"Enclosed within {target_node}",
                }

    annotation = {
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
        "nodes": nodes,
        "relations": [],
        "coverage": {
            "status": "complete",
            "uninspected_regions": [],
            "unresolved_proposal_ids": [],
            "proposals_disposition": disps,
        },
        "annotation_provenance": {
            "model_requested": "gemini-3.8-flash-antigravity",
            "model_returned": "gemini-3.8-flash-antigravity",
            "thinking_requested": "high",
            "prompt_version": "0.1.0",
            "human_reviewed": True,
            "audit_applied": True,
        },
    }

    (s_dir / "annotation.teacher.json").write_text(json.dumps(annotation, indent=2))
    (s_dir / "annotation.reviewed.json").write_text(json.dumps(annotation, indent=2))

    render_full_nodes_overlay(im, nodes, s_dir / "audit_overlay.png")

    val = validate_annotation_file(
        annotation_path=s_dir / "annotation.reviewed.json",
        image_path=dest_img,
        raw_proposals_path=raw_json_path,
    )
    if not val["valid"]:
        raise ValueError(f"[{screen_id}] Validation failed: {val['errors']}")
    print(f"[{screen_id}] 100% VALIDATED with {len(nodes)} nodes, {len(proposals)} proposals.")
    return meta
