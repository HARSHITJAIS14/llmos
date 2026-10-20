"""Comprehensive validator for contextual screen perception annotations."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Tuple
import jsonschema
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_FILE = REPO_ROOT / "screen_understanding/dataset/schema/annotation.schema.json"


def validate_acyclic_hierarchy(nodes: List[Dict]) -> Tuple[bool, List[str]]:
    """Verify that parent links form an acyclic tree with exactly one root."""
    errors = []
    node_ids = {n["id"] for n in nodes}
    roots = [n for n in nodes if n.get("parent_id") is None]

    if len(roots) != 1:
        errors.append(f"Expected exactly 1 root node with parent_id=None, found {len(roots)}")
    elif roots[0]["id"] != "n_0000":
        errors.append(f"Root node must have id 'n_0000', got {roots[0]['id']}")

    parent_map = {n["id"]: n.get("parent_id") for n in nodes}

    # Check for nonexistent parents
    for nid, pid in parent_map.items():
        if pid is not None and pid not in node_ids:
            errors.append(f"Node {nid} references nonexistent parent {pid}")

    # Check for cycles
    for nid in node_ids:
        visited = set()
        curr = nid
        while curr is not None:
            if curr in visited:
                errors.append(f"Cycle detected in parent hierarchy containing node {curr}")
                break
            visited.add(curr)
            curr = parent_map.get(curr)

    return len(errors) == 0, errors


def validate_coordinates(nodes: List[Dict], width: int, height: int) -> Tuple[bool, List[str]]:
    """Ensure all bounding boxes have valid dimensions within image bounds."""
    errors = []
    for n in nodes:
        nid = n["id"]
        box = n.get("bbox")
        if not isinstance(box, list) or len(box) != 4:
            errors.append(f"Node {nid} has invalid bbox format: {box}")
            continue
        l, t, r, b = box
        if l >= r:
            errors.append(f"Node {nid} has left >= right: {box}")
        if t >= b:
            errors.append(f"Node {nid} has top >= bottom: {box}")
        if l < 0 or t < 0 or r > width or b > height:
            # Allow tolerance of up to 2 pixels for rounding
            if l < -2 or t < -2 or r > width + 2 or b > height + 2:
                errors.append(f"Node {nid} bbox is out of image bounds ([0, 0, {width}, {height}]): {box}")

    return len(errors) == 0, errors


def validate_proposals_coverage(annotation: Dict, raw_proposals: Dict) -> Tuple[bool, List[str]]:
    """Ensure all raw proposals have a recorded disposition."""
    errors = []
    raw_list = raw_proposals.get("proposals", [])
    raw_ids = {p["id"] for p in raw_list}

    cov = annotation.get("coverage", {})
    dispositions = cov.get("proposals_disposition", {})

    missing_dispositions = raw_ids - set(dispositions.keys())
    if missing_dispositions:
        errors.append(f"{len(missing_dispositions)} proposals missing explicit disposition: {list(missing_dispositions)[:5]}...")

    return len(errors) == 0, errors


def validate_annotation_file(
    annotation_path: Path,
    image_path: Path,
    raw_proposals_path: Optional[Path] = None,
) -> Dict:
    """Validate annotation against schema, geometry, hierarchy, and image hash."""
    schema = json.loads(SCHEMA_FILE.read_text())
    ann = json.loads(annotation_path.read_text())

    errors = []
    warnings = []

    # 1. JSON Schema validation
    try:
        jsonschema.validate(instance=ann, schema=schema)
    except jsonschema.ValidationError as e:
        errors.append(f"JSON Schema validation error: {e.message} at path {list(e.path)}")

    # 2. Image hash and dimensions check
    im = Image.open(image_path)
    actual_w, actual_h = im.size
    actual_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()

    rec_img = ann.get("image", {})
    if rec_img.get("width") != actual_w or rec_img.get("height") != actual_h:
        errors.append(f"Dimension mismatch: image is ({actual_w}, {actual_h}) vs recorded ({rec_img.get('width')}, {rec_img.get('height')})")
    if rec_img.get("sha256") != actual_hash:
        errors.append(f"SHA-256 mismatch for image: recorded {rec_img.get('sha256')} != actual {actual_hash}")

    # 3. Hierarchy check
    nodes = ann.get("nodes", [])
    h_ok, h_errs = validate_acyclic_hierarchy(nodes)
    errors.extend(h_errs)

    # 4. Coordinate validity
    c_ok, c_errs = validate_coordinates(nodes, actual_w, actual_h)
    errors.extend(c_errs)

    # 5. Proposal dispositions
    if raw_proposals_path and raw_proposals_path.exists():
        raw_p = json.loads(raw_proposals_path.read_text())
        p_ok, p_errs = validate_proposals_coverage(ann, raw_p)
        errors.extend(p_errs)

    is_valid = len(errors) == 0
    report = {
        "valid": is_valid,
        "screen_id": ann.get("screen_id"),
        "node_count": len(nodes),
        "errors": errors,
        "warnings": warnings,
        "schema_version": ann.get("schema_version"),
        "timestamp": Path(annotation_path).stat().st_mtime,
    }

    # Save to validation.json alongside annotation
    val_path = annotation_path.parent / "validation.json"
    val_path.write_text(json.dumps(report, indent=2) + "\n")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotation", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--proposals", type=Path, default=None)
    args = parser.parse_args()

    rep = validate_annotation_file(args.annotation, args.image, args.proposals)
    print(f"Validation result: {'PASSED' if rep['valid'] else 'FAILED'}")
    if not rep["valid"]:
        for e in rep["errors"]:
            print(" - Error:", e)
    else:
        print(f"All checks passed ({rep['node_count']} nodes).")
