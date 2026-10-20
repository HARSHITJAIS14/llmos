"""The menu bar as a command channel (implementation.md §6.9).

Measured: reading 3 menus takes 0.5–2.2 ms and items are readable while closed. Menu
presses don't depend on the keyboard layout or on coordinates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import raw
from .normalize import fold, norm

ITEM_ATTRS = ["AXRole", "AXTitle", "AXEnabled", "AXMenuItemMarkChar", "AXMenuItemCmdChar",
              "AXMenuItemCmdModifiers", "AXMenuItemCmdVirtualKey", "AXChildren"]

# AXMenuItemCmdModifiers bits: 0 = Cmd only, 1 = +Shift, 2 = +Option, 4 = +Control, 8 = no Cmd.
_VKEY_NAMES = {36: "return", 48: "tab", 49: "space", 51: "delete", 53: "escape", 117: "forwarddelete",
               123: "left", 124: "right", 125: "down", 126: "up", 115: "home", 119: "end",
               116: "pageup", 121: "pagedown", 122: "f1", 120: "f2", 99: "f3", 118: "f4", 96: "f5",
               97: "f6", 98: "f7", 100: "f8", 101: "f9", 109: "f10", 103: "f11", 111: "f12"}


@dataclass(slots=True)
class MenuItem:
    path: tuple[str, ...]
    title: str
    enabled: bool
    checked: bool
    shortcut: str
    ref: Any = None

    def to_json(self) -> dict:
        return {"path": list(self.path), "enabled": self.enabled, "checked": self.checked,
                "shortcut": self.shortcut}


def format_shortcut(a: dict) -> str:
    char = a.get("AXMenuItemCmdChar")
    mods = a.get("AXMenuItemCmdModifiers")
    vkey = a.get("AXMenuItemCmdVirtualKey")
    key = ""
    if isinstance(char, str) and char.strip():
        key = char.strip().lower()
    elif isinstance(vkey, int) and vkey in _VKEY_NAMES:
        key = _VKEY_NAMES[vkey]
    if not key:
        return ""
    mods = int(mods) if isinstance(mods, (int, float)) else 0
    parts = []
    if not mods & 8:
        parts.append("cmd")
    if mods & 4:
        parts.append("ctrl")
    if mods & 2:
        parts.append("opt")
    if mods & 1:
        parts.append("shift")
    return "+".join(parts + [key])


def read_menus(pid: int, max_depth: int = 2, skip_apple: bool = True) -> list[MenuItem]:
    app = raw.app_element(pid)
    err, a = raw.batch(app, ["AXMenuBar"])
    bar = a.get("AXMenuBar")
    if not raw.is_ref(bar):
        return []
    err, b = raw.batch(bar, ["AXChildren"])
    items: list[MenuItem] = []
    for i, top in enumerate(b.get("AXChildren") or []):
        if not raw.is_ref(top) or (skip_apple and i == 0):
            continue
        err, t = raw.batch(top, ["AXTitle", "AXChildren"])
        title = norm(t.get("AXTitle") if isinstance(t.get("AXTitle"), str) else "")
        if not title:
            continue
        for menu in t.get("AXChildren") or []:
            if raw.is_ref(menu):
                _read(menu, (title,), items, 1, max_depth)
    return items


def _read(menu_ref: Any, prefix: tuple[str, ...], items: list[MenuItem], depth: int, max_depth: int) -> None:
    err, m = raw.batch(menu_ref, ["AXChildren"])
    for it in m.get("AXChildren") or []:
        if not raw.is_ref(it):
            continue
        err, a = raw.batch(it, ITEM_ATTRS)
        title = norm(a.get("AXTitle") if isinstance(a.get("AXTitle"), str) else "")
        if not title:
            continue                                               # separators
        path = prefix + (title,)
        mark = a.get("AXMenuItemMarkChar")
        items.append(MenuItem(path=path, title=title, enabled=a.get("AXEnabled") is not False,
                              checked=bool(isinstance(mark, str) and mark.strip()),
                              shortcut=format_shortcut(a), ref=it))
        if depth < max_depth:
            for sub in a.get("AXChildren") or []:
                if raw.is_ref(sub):
                    _read(sub, path, items, depth + 1, max_depth)


def _key(s: str) -> str:
    return fold(s.replace("…", "...")).rstrip(".").strip()


def find_item(items: list[MenuItem], path: list[str] | tuple[str, ...]) -> MenuItem | None:
    want = tuple(_key(p) for p in path)
    for it in items:
        if tuple(_key(p) for p in it.path) == want:
            return it
    # Allow the last element to match on its own when the menu names were omitted.
    if len(want) == 1:
        hits = [it for it in items if _key(it.title) == want[0]]
        if len(hits) == 1:
            return hits[0]
    return None


def press(pid: int, path: list[str], items: list[MenuItem] | None = None) -> tuple[bool, str]:
    items = items if items is not None else read_menus(pid)
    item = find_item(items, path)
    if item is None:
        # Some apps build menus on open: open the top menu, re-read it, press, else cancel.
        bar_item = _top_item(pid, path[0]) if path else None
        if bar_item is not None:
            raw.perform(bar_item, "AXPress")
            fresh = read_menus(pid)
            item = find_item(fresh, path)
            if item is None:
                raw.perform(bar_item, "AXCancel")
                return False, f"menu item not found: {' > '.join(path)}"
        else:
            return False, f"menu not found: {path[0] if path else ''}"
    if not item.enabled:
        return False, f"menu item disabled: {' > '.join(item.path)}"
    err = raw.perform(item.ref, "AXPress")
    return err == raw.OK, ("" if err == raw.OK else f"AXPress failed ({err})")


def _top_item(pid: int, title: str) -> Any:
    err, a = raw.batch(raw.app_element(pid), ["AXMenuBar"])
    bar = a.get("AXMenuBar")
    if not raw.is_ref(bar):
        return None
    err, b = raw.batch(bar, ["AXChildren"])
    for top in b.get("AXChildren") or []:
        err, t = raw.batch(top, ["AXTitle"])
        if _key(t.get("AXTitle") or "") == _key(title):
            return top
    return None


def top_commands(items: list[MenuItem], limit: int = 25) -> list[MenuItem]:
    """The commands worth showing the planner: enabled, from the main menus, shortcuts first."""
    skip_menus = {"help", "window"}
    keep = [it for it in items if it.enabled and it.path and _key(it.path[0]) not in skip_menus]
    keep.sort(key=lambda it: (0 if it.shortcut else 1, len(it.path)))
    return keep[:limit]
