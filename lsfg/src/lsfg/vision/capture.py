"""Window capture into memory (implementation.md §7).

Measured: 10.5 ms for a 2560×1440 window at nominal resolution (pixels = points).
CGWindowListCreateImage is deprecated since macOS 14 but works on this machine;
ScreenCaptureKit is the planned fallback behind this same interface.
"""
from __future__ import annotations

import hashlib
from typing import Any

import Quartz

from ..types import Rect


def capture_window(window_id: int) -> Any:
    return Quartz.CGWindowListCreateImage(
        Quartz.CGRectNull, Quartz.kCGWindowListOptionIncludingWindow, int(window_id),
        Quartz.kCGWindowImageBoundsIgnoreFraming | Quartz.kCGWindowImageNominalResolution)


def size(img: Any) -> tuple[int, int]:
    return int(Quartz.CGImageGetWidth(img)), int(Quartz.CGImageGetHeight(img))


def crop(img: Any, region: Rect, window_bounds: Rect) -> tuple[Any, Rect]:
    """Crop to a screen-space rect. Returns the crop and the screen rect it actually covers."""
    iw, ih = size(img)
    wx, wy, ww, wh = window_bounds
    sx, sy = iw / ww if ww else 1.0, ih / wh if wh else 1.0
    x0 = max(0.0, (region[0] - wx) * sx)
    y0 = max(0.0, (region[1] - wy) * sy)
    x1 = min(float(iw), (region[0] + region[2] - wx) * sx)
    y1 = min(float(ih), (region[1] + region[3] - wy) * sy)
    if x1 <= x0 or y1 <= y0:
        return None, region
    c = Quartz.CGImageCreateWithImageInRect(img, Quartz.CGRectMake(x0, y0, x1 - x0, y1 - y0))
    return c, (wx + x0 / sx, wy + y0 / sy, (x1 - x0) / sx, (y1 - y0) / sy)


def pixel_hash(img: Any, row_step: int = 8) -> str:
    """blake2b over every 8th row, so a 14 MB frame hashes in about a millisecond."""
    data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(img))
    bpr = int(Quartz.CGImageGetBytesPerRow(img))
    h = int(Quartz.CGImageGetHeight(img))
    mv = memoryview(bytes(data))
    d = hashlib.blake2b(digest_size=16)
    for row in range(0, h, row_step):
        d.update(mv[row * bpr:(row + 1) * bpr])
    return d.hexdigest()
