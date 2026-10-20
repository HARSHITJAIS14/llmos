"""Apple Vision OCR on in-memory captures (implementation.md §7).

Measured: fast 14–15 ms per window, accurate 117–147 ms. We keep `fast`. One cache entry per
(window, crop) keyed by a pixel hash; a stale coordinate would be a misplaced click. OCR
geometry is never part of any change signature (LATENCY R5).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import objc
import Vision

from ..types import Rect
from ..ax.normalize import fold, norm
from . import capture


@dataclass(slots=True)
class TextBox:
    text: str
    confidence: float
    bounds: Rect                                    # global screen points

    @property
    def center(self) -> tuple[float, float]:
        x, y, w, h = self.bounds
        return (x + w / 2.0, y + h / 2.0)


def _iou(a: Rect, b: Rect) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    w = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    h = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = w * h
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def recognize(img: Any, screen_rect: Rect, level: str = "fast", min_conf: float = 0.45,
              max_boxes: int = 200) -> list[TextBox]:
    iw, ih = capture.size(img)
    sx, sy, sw, sh = screen_rect
    boxes: list[TextBox] = []
    with objc.autorelease_pool():
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(1 if level == "fast" else 0)
        req.setUsesLanguageCorrection_(False)
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
        ok = handler.performRequests_error_([req], None)
        if isinstance(ok, tuple):
            ok = ok[0]
        if not ok:
            return []
        for obs in list(req.results() or []):
            cands = obs.topCandidates_(1)
            if not cands:
                continue
            c = cands[0]
            text = norm(str(c.string() or ""))
            conf = float(c.confidence())
            if not text or not math.isfinite(conf) or conf < min_conf:
                continue
            bb = obs.boundingBox()
            x, y, w, h = float(bb.origin.x), float(bb.origin.y), float(bb.size.width), float(bb.size.height)
            # Vision: normalized, origin bottom-left → global points, origin top-left.
            boxes.append(TextBox(text=text[:240], confidence=round(conf, 3),
                                 bounds=(sx + x * sw, sy + (1.0 - y - h) * sh, max(1.0, w * sw), max(1.0, h * sh))))
    kept: list[TextBox] = []
    for b in sorted(boxes, key=lambda b: -b.confidence):          # collapse duplicate readings
        if all(_iou(b.bounds, k.bounds) < 0.55 for k in kept):
            kept.append(b)
        if len(kept) >= max_boxes:
            break
    kept.sort(key=lambda b: (round(b.bounds[1] / 8), b.bounds[0]))
    return kept


class OCR:
    def __init__(self) -> None:
        self._cache: dict[tuple, tuple[str, list[TextBox]]] = {}

    def read(self, window_id: int, window_bounds: Rect, region: Rect | None = None,
             level: str = "fast") -> list[TextBox]:
        img = capture.capture_window(window_id)
        if img is None:
            return []
        rect = window_bounds
        if region is not None:
            img, rect = capture.crop(img, region, window_bounds)
            if img is None:
                return []
        key = (window_id, tuple(round(v) for v in rect), level)
        h = capture.pixel_hash(img)
        hit = self._cache.get(key)
        if hit is not None and hit[0] == h:
            return hit[1]
        boxes = recognize(img, rect, level)
        self._cache = {k: v for k, v in self._cache.items() if k[0] != window_id}   # one entry per window
        self._cache[key] = (h, boxes)
        return boxes


def contains(boxes: list[TextBox], text: str) -> bool:
    want = fold(text)
    if not want:
        return False
    joined = fold(" ".join(b.text for b in boxes))
    return any(want in fold(b.text) for b in boxes) or want in joined
