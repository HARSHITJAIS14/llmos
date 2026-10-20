"""Accessibility actions (implementation.md §9.2). They never activate the app.

Value coercion (dates, bools, numbers) is ported from arc-cua's _coerce_settable_ax_value (MIT).
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from ..types import Node
from ..ax import raw


def press(node: Node) -> int:
    acts = node.actions or frozenset()
    for name in ("AXPress", "AXConfirm", "AXOpen"):
        if not acts or name in acts:
            err = raw.perform(node.ref, name)
            if err == raw.OK or acts:
                return err
    return raw.ACTION_UNSUPPORTED


def perform(node: Node, action: str) -> int:
    return raw.perform(node.ref, action)


def focus(node: Node) -> int:
    return raw.set_attr(node.ref, "AXFocused", True)


def set_selected(node: Node) -> int:
    return raw.set_attr(node.ref, "AXSelected", True)


def set_expanded(node: Node, expanded: bool = True) -> int:
    return raw.set_attr(node.ref, "AXExpanded", bool(expanded))


def select_all(node: Node) -> int:
    err, n = raw.attr(node.ref, "AXNumberOfCharacters")
    if err != raw.OK or not isinstance(n, int):
        v = node.value if isinstance(node.value, str) else ""
        n = node.value_len or len(v)
    return raw.set_attr(node.ref, "AXSelectedTextRange", raw.make_range(0, int(n)))


def caret_to_end(node: Node) -> int:
    err, n = raw.attr(node.ref, "AXNumberOfCharacters")
    if err != raw.OK or not isinstance(n, int):
        n = node.value_len or (len(node.value) if isinstance(node.value, str) else 0)
    return raw.set_attr(node.ref, "AXSelectedTextRange", raw.make_range(int(n), 0))


def read_value(node: Node) -> tuple[int, Any]:
    return raw.attr(node.ref, "AXValue")


def set_value(node: Node, wanted: Any) -> int:
    err, current = raw.attr(node.ref, "AXValue")
    try:
        value = coerce_settable_value(current, wanted)
    except ValueError:
        return raw.ILLEGAL_ARGUMENT
    return raw.set_attr(node.ref, "AXValue", value)


def _parse_time(text: str) -> tuple[int, int] | None:
    m = re.fullmatch(r"(\d{1,2})(?::(\d{1,2}))?\s*([ap])?\.?m?\.?", text.strip().lower())
    if not m:
        return None
    hour, minute, suffix = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if minute > 59:
        return None
    if suffix:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if suffix == "p" else 0)
    elif not 0 <= hour <= 23:
        return None
    return hour, minute


def coerce_settable_value(current: Any, wanted: Any) -> Any:
    if isinstance(current, str) and _looks_iso(current) and isinstance(wanted, str):
        base = datetime.fromisoformat(current)
        t = _parse_time(wanted)
        target = base.replace(hour=t[0], minute=t[1], second=0, microsecond=0) if t else datetime.fromisoformat(wanted)
        if target.tzinfo is None:
            target = target.replace(tzinfo=base.tzinfo)
        import Foundation
        return Foundation.NSDate.dateWithTimeIntervalSince1970_(target.timestamp())
    if isinstance(current, bool):
        if isinstance(wanted, str):
            w = wanted.strip().lower()
            if w in ("true", "yes", "on", "1", "enabled"):
                return True
            if w in ("false", "no", "off", "0", "disabled"):
                return False
            raise ValueError(f"not a boolean: {wanted!r}")
        return bool(wanted)
    if isinstance(current, int) and not isinstance(current, bool):
        return int(wanted)
    if isinstance(current, float):
        return float(wanted)
    return str(wanted) if not isinstance(wanted, (int, float, bool)) else wanted


def _looks_iso(s: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", s))
