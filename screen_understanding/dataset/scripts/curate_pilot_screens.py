"""Curate and render pristine, safe macOS screenshots for the 30-screen pilot dataset."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[3]
PILOT_DIR = REPO_ROOT / "screen_understanding/dataset/pilot_v001"
SCREENS_DIR = PILOT_DIR / "screens"


def draw_macos_window_frame(
    width: int,
    height: int,
    title: str = "",
    dark_mode: bool = True,
    has_sidebar: bool = False,
    sidebar_width: int = 400,
) -> Tuple[Image.Image, ImageDraw.Draw]:
    """Render a pixel-perfect macOS window canvas with native titlebar and traffic lights."""
    bg_color = (24, 24, 27) if dark_mode else (244, 244, 246)
    tb_color = (39, 39, 42) if dark_mode else (232, 232, 235)
    border_color = (63, 63, 70) if dark_mode else (212, 212, 216)
    text_color = (244, 244, 245) if dark_mode else (24, 24, 27)

    im = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(im)

    # Top titlebar
    tb_h = 100
    draw.rectangle([0, 0, width, tb_h], fill=tb_color)
    draw.line([0, tb_h, width, tb_h], fill=border_color, width=2)

    # Traffic lights (red, yellow, green)
    y_center = 50
    draw.ellipse([30, y_center - 16, 62, y_center + 16], fill="#ff5f56") # Red
    draw.ellipse([75, y_center - 16, 107, y_center + 16], fill="#ffbd2e") # Yellow
    draw.ellipse([120, y_center - 16, 152, y_center + 16], fill="#27c93f") # Green

    # Window title if present
    if title:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/SFProDisplay-Semibold.otf", 26)
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), title, font=font)
        tw = bbox[2] - bbox[0]
        tx = (width - tw) // 2
        draw.text((tx, y_center - 14), title, fill=text_color, font=font)

    # Sidebar line if present
    if has_sidebar:
        sb_bg = (32, 32, 36) if dark_mode else (238, 238, 241)
        draw.rectangle([0, tb_h, sidebar_width, height], fill=sb_bg)
        draw.line([sidebar_width, tb_h, sidebar_width, height], fill=border_color, width=2)

    return im, draw
