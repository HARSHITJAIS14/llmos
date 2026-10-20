"""What leaves the machine (implementation.md §16.3).

mask(): content-region labels become shape tokens ("Wwww 99"), except strings that match a task
input (needed to match). Used only when privacy.mask_content is on.
"""
from __future__ import annotations

import re

from ..ax.normalize import fold


def shape(text: str) -> str:
    return re.sub(r"[A-Za-z]+", lambda m: "W" + "w" * (len(m.group(0)) - 1),
                  re.sub(r"\d", "9", text))


def mask(text: str, keep: list[str]) -> str:
    f = fold(text)
    if any(k and fold(k) in f for k in keep):
        return text
    return shape(text)


EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]*)*")   # also truncated ones ("a@gmail.")


def scrub(text: str, keep: str = "") -> str:
    """Emails never leave the machine unless the task itself contains that address."""
    if not text or "@" not in text:
        return text
    return EMAIL.sub(lambda m: m.group(0) if m.group(0).lower() in keep.lower() else "<email>", text)
