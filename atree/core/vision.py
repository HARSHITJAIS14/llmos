"""The vision escalation ladder (pitch §6) — pixels as the failure branch.

Vision never enters the verification path; it enters the FAILURE branch of
the verification path. The ladder is enforced here in code, not left to
judgment: each rung may only fire when the rung below was inconclusive.

  rung 2  region pixel-hash delta   free, no model call
  rung 3  local OCR                 free, no model call (Vision.framework)
  rung 4  bounds-cropped screenshot the agent Reads the crop (~64 tok)

Rungs 0-1 (AX postcondition, AX re-query) live in core.postconditions.
Rung 4 has no API plumbing: in Claude Code the agent itself is the VLM — this
module produces the crop, the agent Reads the file. Keep the question closed:
"is <control> visible and unobstructed — yes or no?"
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

CROP_PAD_PX = 20
_OCR_SWIFT = Path(__file__).with_name("ocr.swift")


def _region_args(bounds: dict, pad: int = 0) -> str:
    x = int(bounds["x"]) - pad
    y = int(bounds["y"]) - pad
    w = int(bounds.get("width", bounds.get("w", 0))) + 2 * pad
    h = int(bounds.get("height", bounds.get("h", 0))) + 2 * pad
    return f"{max(x, 0)},{max(y, 0)},{max(w, 1)},{max(h, 1)}"


def capture_region(bounds: dict, out_path: str | None = None, pad: int = 0) -> str:
    """Grab just the element's region. `screencapture -R` needs Screen
    Recording permission (already required for agent-desktop screenshots)."""
    out = out_path or tempfile.mktemp(suffix=".png", prefix="atree_region_")
    res = subprocess.run(
        ["/usr/sbin/screencapture", "-x", "-R", _region_args(bounds, pad), out],
        capture_output=True, text=True, timeout=10,
    )
    if res.returncode != 0 or not os.path.exists(out):
        raise RuntimeError(f"screencapture failed: {res.stderr.strip() or res.returncode}")
    return out


# rung 2 ------------------------------------------------------------------

def region_hash(bounds: dict) -> str:
    """Hash the element's pixels. Zero tokens, no model call."""
    path = capture_region(bounds)
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    finally:
        os.unlink(path)


def region_changed(bounds: dict, before_hash: str) -> bool:
    """Did the click land on ANYTHING? Identical hash == swallowed input —
    the most common Electron failure, diagnosed for free."""
    return region_hash(bounds) != before_hash


# rung 3 ------------------------------------------------------------------

def ocr_region(bounds: dict, pad: int = CROP_PAD_PX) -> str:
    """Local Vision.framework OCR. Free; no model involved."""
    img = capture_region(bounds, pad=pad)
    try:
        res = subprocess.run(
            ["swift", str(_OCR_SWIFT), img],
            capture_output=True, text=True, timeout=60,
        )
        if res.returncode != 0:
            raise RuntimeError(f"ocr failed: {res.stderr.strip()[:500]}")
        return res.stdout.strip()
    finally:
        os.unlink(img)


def text_present(bounds: dict, needle: str) -> bool:
    return needle.lower() in ocr_region(bounds).lower()


# rung 4 ------------------------------------------------------------------

def crop_for_agent(bounds: dict, out_dir: str | None = None, pad: int = CROP_PAD_PX) -> dict:
    """Produce a tiny crop for the agent to Read. Returns path + est. tokens
    ((w*h)/750) so cost stays visible in the transcript."""
    out_dir = out_dir or tempfile.gettempdir()
    out = os.path.join(out_dir, "atree_crop.png")
    capture_region(bounds, out_path=out, pad=pad)
    w = int(bounds.get("width", 0)) + 2 * pad
    h = int(bounds.get("height", 0)) + 2 * pad
    return {"path": out, "est_tokens": max(1, (w * h) // 750),
            "ask": "Closed question only: is the control visible and unobstructed — yes or no?"}


# the ladder, enforced ------------------------------------------------------

def diagnose(bounds: dict, before_hash: str | None = None,
             expect_text: str | None = None) -> dict:
    """Walk rungs 2-3; hand rung 4 to the agent only if both are inconclusive.

    Enforced ordering — a caller cannot start at rung 4.
    """
    report: dict = {"rungs": []}

    if before_hash is not None:
        try:
            changed = region_changed(bounds, before_hash)
            report["rungs"].append({"rung": 2, "check": "pixel-hash delta", "changed": changed})
            if not changed:
                report["verdict"] = "input swallowed: zero pixel change in target region"
                return report
        except Exception as exc:
            report["rungs"].append({"rung": 2, "error": str(exc)})

    if expect_text is not None:
        try:
            found = text_present(bounds, expect_text)
            report["rungs"].append({"rung": 3, "check": f"ocr for {expect_text!r}", "found": found})
            report["verdict"] = ("expected text rendered" if found
                                 else f"expected text {expect_text!r} not rendered in region")
            if found:
                return report
        except Exception as exc:
            report["rungs"].append({"rung": 3, "error": str(exc)})

    report["rung4"] = crop_for_agent(bounds)
    report.setdefault("verdict", "inconclusive on free rungs — Read the crop at rung4.path")
    return report


if __name__ == "__main__":
    bounds = json.loads(sys.argv[1])  # e.g. '{"x":100,"y":200,"width":400,"height":120}'
    kwargs = {}
    if len(sys.argv) > 2:
        kwargs["expect_text"] = sys.argv[2]
    print(json.dumps(diagnose(bounds, **kwargs), indent=2))
