"""Candidate bounding box detector runner (supports remote gpu3 and local execution)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Dict, List, Optional
from PIL import Image, ImageDraw, ImageFont

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))


def draw_proposal_overlay(
    image: Image.Image,
    proposals: List[Dict],
    out_path: Path,
    box_color: str = "#2563eb",
    label_bg_color: str = "#2563eb",
    text_color: str = "#ffffff",
):
    """Render a clean neutral overlay showing bounding boxes and stable proposal IDs."""
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for p in proposals:
        l, t, r, b = p["bbox"]
        pid = p["id"]
        draw.rectangle([l, t, r, b], outline=box_color, width=2)
        # Background badge for label
        badge_w = 48
        badge_h = 16
        draw.rectangle([l, max(0, t - badge_h), l + badge_w, t], fill=label_bg_color)
        draw.text((l + 3, max(0, t - badge_h) + 2), pid, fill=text_color, font=font)

    overlay.save(out_path, format="PNG")


def run_detector_local(
    image_path: Path,
    weights_path: Path,
    device: str = "cpu",
    conf: float = 0.10,
    iou: float = 0.10,
) -> Dict:
    """Run local detector using YOLOv9Detector or Ultralytics."""
    omni_dir = REPO_ROOT / "vlm_testing/click_omniparser/OmniParser"
    if str(omni_dir) not in sys.path:
        sys.path.append(str(omni_dir))
    from util.yolov9 import YOLOv9Detector

    im = Image.open(image_path).convert("RGB")
    w, h = im.size
    weights_hash = hashlib.sha256(weights_path.read_bytes()).hexdigest()

    detector = YOLOv9Detector(str(weights_path), device=device)
    res = detector.predict(im, imgsz=1280, conf=conf, iou=iou)[0]

    proposals = []
    for idx, (box, score) in enumerate(zip(res.boxes.xyxy.cpu().tolist(), res.boxes.conf.cpu().tolist()), start=1):
        pid = f"d_{idx:04d}"
        proposals.append({
            "id": pid,
            "bbox": [round(float(v), 2) for v in box],
            "label": "icon",
            "confidence": round(float(score), 4),
        })

    return {
        "detector": "OmniParser-v2.0-icon_detect",
        "device": device,
        "weights_path": str(weights_path),
        "weights_sha256": weights_hash,
        "image_size": [w, h],
        "conf_threshold": conf,
        "iou_threshold": iou,
        "proposal_count": len(proposals),
        "proposals": proposals,
    }


def run_detector_remote_gpu3(
    image_path: Path,
    remote_host: str = "gpu3",
    remote_workdir: str = "/data/harshitj23/screen-understanding",
    weights_name: str = "omniparser-detector.pt",
    conf: float = 0.10,
    iou: float = 0.10,
) -> Dict:
    """Run detector on remote gpu3 via SSH."""
    im = Image.open(image_path).convert("RGB")
    w, h = im.size

    img_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()[:16]
    remote_img = f"{remote_workdir}/runs/tmp_{img_hash}.png"
    remote_out = f"{remote_workdir}/runs/tmp_{img_hash}_out.json"

    # Copy image to remote
    subprocess.run(["scp", str(image_path), f"{remote_host}:{remote_img}"], check=True)

    remote_script = f"""
source /data/harshitj23/miniforge3/etc/profile.d/conda.sh
conda activate /data/harshitj23/envs/perception-py311
python -c '
import json, hashlib, time
from pathlib import Path
from ultralytics import YOLO
from PIL import Image

weights_file = Path("{remote_workdir}/models/{weights_name}")
weights_hash = hashlib.sha256(weights_file.read_bytes()).hexdigest()
model = YOLO(str(weights_file))

im = Image.open("{remote_img}").convert("RGB")
res = model.predict(im, imgsz=1280, conf={conf}, iou={iou}, device=0, verbose=False)[0]

proposals = []
for idx, (b, s, c) in enumerate(zip(res.boxes.xyxy.cpu().tolist(), res.boxes.conf.cpu().tolist(), res.boxes.cls.cpu().tolist()), start=1):
    proposals.append({{
        "id": f"d_{{idx:04d}}",
        "bbox": [round(float(v), 2) for v in b],
        "label": model.names[int(c)],
        "confidence": round(float(s), 4)
    }})

output = {{
    "detector": "{weights_name}",
    "device": "cuda:0",
    "weights_sha256": weights_hash,
    "image_size": list(im.size),
    "conf_threshold": {conf},
    "iou_threshold": {iou},
    "proposal_count": len(proposals),
    "proposals": proposals
}}
Path("{remote_out}").write_text(json.dumps(output, indent=2))
'
"""
    subprocess.run(["ssh", remote_host, remote_script], check=True)

    # Copy back output
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        subprocess.run(["scp", f"{remote_host}:{remote_out}", str(tmp_path)], check=True)
        data = json.loads(tmp_path.read_text())
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
        subprocess.run(["ssh", remote_host, f"rm -f {remote_img} {remote_out}"])

    return data


def detect_proposals(
    image_path: Path,
    out_dir: Path,
    use_remote: bool = True,
    local_weights: Optional[Path] = None,
) -> Dict:
    """Main entry to run detector and save raw.json and overlay.png."""
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_json_path = out_dir / "raw.json"
    overlay_path = out_dir / "overlay.png"

    result = None
    if use_remote:
        try:
            result = run_detector_remote_gpu3(image_path)
        except Exception as e:
            print(f"[Warning] Remote gpu3 detector failed: {e}. Falling back to local execution.")

    if result is None:
        if local_weights is None:
            local_weights = REPO_ROOT / "vlm_testing/click_omniparser/OmniParser/weights/icon_detect_v3/model.pt"
        result = run_detector_local(image_path, local_weights, device="cpu")

    raw_json_path.write_text(json.dumps(result, indent=2) + "\n")

    # Render overlay
    im = Image.open(image_path).convert("RGB")
    draw_proposal_overlay(im, result["proposals"], overlay_path)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--local", action="store_true")
    args = parser.parse_args()

    res = detect_proposals(args.image, args.output_dir, use_remote=not args.local)
    print(f"Detected {res['proposal_count']} proposals. Saved to {args.output_dir}")
