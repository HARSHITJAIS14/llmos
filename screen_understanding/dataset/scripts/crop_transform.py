"""Coordinate transformations and crop geometry for contextual screen perception dataset."""
from __future__ import annotations

import math
from typing import Dict, List, Tuple, Union
from PIL import Image


class CropTransform:
    """Manages coordinate transformations between source screenshot pixels and crop pixels."""

    def __init__(
        self,
        source_origin: Tuple[float, float],
        padding: Tuple[float, float] = (0.0, 0.0),
        scale: Tuple[float, float] = (1.0, 1.0),
        crop_box_in_source: Tuple[float, float, float, float] = None,
        crop_image_size: Tuple[int, int] = None,
    ):
        """
        source_origin: (x0, y0) in source screenshot pixels
        padding: (px, py) applied before scaling / cropping
        scale: (sx, sy) scaling factors (crop_pixels / unscaled_crop_pixels)
        crop_box_in_source: (x0, y0, x1, y1) in source pixels
        crop_image_size: (width, height) of the resulting crop image
        """
        self.x0, self.y0 = float(source_origin[0]), float(source_origin[1])
        self.px, self.py = float(padding[0]), float(padding[1])
        self.sx, self.sy = float(scale[0]), float(scale[1])
        if self.sx <= 0 or self.sy <= 0:
            raise ValueError(f"Scales must be positive, got ({self.sx}, {self.sy})")
        self.crop_box_in_source = crop_box_in_source
        self.crop_image_size = crop_image_size

    def to_source_point(self, crop_x: float, crop_y: float) -> Tuple[float, float]:
        """Convert crop coordinate to source screenshot pixels."""
        src_x = self.x0 + (crop_x - self.px) / self.sx
        src_y = self.y0 + (crop_y - self.py) / self.sy
        return (src_x, src_y)

    def to_crop_point(self, src_x: float, src_y: float) -> Tuple[float, float]:
        """Convert source screenshot pixel coordinate to crop coordinate."""
        crop_x = (src_x - self.x0) * self.sx + self.px
        crop_y = (src_y - self.y0) * self.sy + self.py
        return (crop_x, crop_y)

    def to_source_box(self, crop_box: List[float]) -> List[float]:
        """Convert [left, top, right, bottom] in crop pixels to source screenshot pixels."""
        if len(crop_box) != 4:
            raise ValueError("Bounding box must have 4 coordinates")
        l, t, r, b = crop_box
        x1, y1 = self.to_source_point(l, t)
        x2, y2 = self.to_source_point(r, b)
        return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]

    def to_crop_box(self, source_box: List[float]) -> List[float]:
        """Convert [left, top, right, bottom] in source screenshot pixels to crop pixels."""
        if len(source_box) != 4:
            raise ValueError("Bounding box must have 4 coordinates")
        l, t, r, b = source_box
        x1, y1 = self.to_crop_point(l, t)
        x2, y2 = self.to_crop_point(r, b)
        return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]

    def to_dict(self) -> Dict[str, Union[float, List[float], List[int]]]:
        return {
            "source_origin": [self.x0, self.y0],
            "padding": [self.px, self.py],
            "scale": [self.sx, self.sy],
            "crop_box_in_source": list(self.crop_box_in_source) if self.crop_box_in_source else None,
            "crop_image_size": list(self.crop_image_size) if self.crop_image_size else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CropTransform:
        return cls(
            source_origin=tuple(data["source_origin"]),
            padding=tuple(data["padding"]),
            scale=tuple(data["scale"]),
            crop_box_in_source=tuple(data["crop_box_in_source"]) if data.get("crop_box_in_source") else None,
            crop_image_size=tuple(data["crop_image_size"]) if data.get("crop_image_size") else None,
        )


def validate_box(box: List[float], max_w: float, max_h: float, min_dim: float = 1.0) -> bool:
    """Validate that box has valid coordinates within image bounds."""
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return False
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in box):
        return False
    l, t, r, b = box
    if l >= r or t >= b:
        return False
    if r - l < min_dim or b - t < min_dim:
        return False
    if l < -5 or t < -5 or r > max_w + 5 or b > max_h + 5:
        # Out of bounds beyond small margin
        return False
    return True


def clip_box(box: List[float], max_w: float, max_h: float) -> List[float]:
    """Clips box to image boundaries [0, 0, max_w, max_h]."""
    l, t, r, b = box
    return [
        max(0.0, min(float(max_w), float(l))),
        max(0.0, min(float(max_h), float(t))),
        max(0.0, min(float(max_w), float(r))),
        max(0.0, min(float(max_h), float(b))),
    ]


def compute_iou(box_a: List[float], box_b: List[float]) -> float:
    """Compute Intersection over Union between two boxes [l, t, r, b]."""
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])
    inter_area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if inter_area <= 0:
        return 0.0
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union_area = area_a + area_b - inter_area
    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def compute_containment(child_box: List[float], parent_box: List[float]) -> float:
    """Fraction of child_box that is inside parent_box."""
    x1 = max(child_box[0], parent_box[0])
    y1 = max(child_box[1], parent_box[1])
    x2 = min(child_box[2], parent_box[2])
    y2 = min(child_box[3], parent_box[3])
    inter_area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    child_area = (child_box[2] - child_box[0]) * (child_box[3] - child_box[1])
    if child_area <= 0:
        return 0.0
    return inter_area / child_area


def extract_padded_crop(
    image: Image.Image,
    box: List[float],
    pad_fraction: float = 0.05,
    min_pad: int = 16,
) -> Tuple[Image.Image, CropTransform]:
    """
    Extract a padded crop from image.
    Returns (cropped_pil_image, CropTransform).
    """
    w, h = image.size
    l, t, r, b = box
    bw = r - l
    bh = b - t

    pad_x = max(min_pad, round(bw * pad_fraction))
    pad_y = max(min_pad, round(bh * pad_fraction))

    crop_l = max(0, int(round(l - pad_x)))
    crop_t = max(0, int(round(t - pad_y)))
    crop_r = min(w, int(round(r + pad_x)))
    crop_b = min(h, int(round(b + pad_y)))

    crop_im = image.crop((crop_l, crop_t, crop_r, crop_b))
    transform = CropTransform(
        source_origin=(crop_l, crop_t),
        padding=(0.0, 0.0),
        scale=(1.0, 1.0),
        crop_box_in_source=(crop_l, crop_t, crop_r, crop_b),
        crop_image_size=crop_im.size,
    )
    return crop_im, transform
