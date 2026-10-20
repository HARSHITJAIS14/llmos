"""Keys and hotkeys (implementation.md §9.6).

Events come from a private event source, so they don't touch the HID key-state table the
Esc kill switch reads. Every post is behind the frontmost guard.
"""
from __future__ import annotations

import time

import Quartz

from ..errors import PlanInvalid
from . import focus

KEYCODES: dict[str, int] = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9, "b": 11,
    "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "o": 31, "u": 32, "i": 34, "p": 35,
    "l": 37, "j": 38, "k": 40, "n": 45, "m": 46,
    "1": 18, "2": 19, "3": 20, "4": 21, "5": 23, "6": 22, "7": 26, "8": 28, "9": 25, "0": 29,
    "=": 24, "-": 27, "]": 30, "[": 33, "'": 39, ";": 41, "\\": 42, ",": 43, "/": 44, ".": 47, "`": 50,
    "return": 36, "enter": 36, "tab": 48, "space": 49, "delete": 51, "backspace": 51, "escape": 53,
    "esc": 53, "forwarddelete": 117, "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
    "left": 123, "right": 124, "down": 125, "up": 126,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98, "f8": 100, "f9": 101,
    "f10": 109, "f11": 103, "f12": 111,
}
MODIFIERS = {
    "cmd": Quartz.kCGEventFlagMaskCommand, "command": Quartz.kCGEventFlagMaskCommand,
    "mod": Quartz.kCGEventFlagMaskCommand, "shift": Quartz.kCGEventFlagMaskShift,
    "opt": Quartz.kCGEventFlagMaskAlternate, "option": Quartz.kCGEventFlagMaskAlternate,
    "alt": Quartz.kCGEventFlagMaskAlternate, "ctrl": Quartz.kCGEventFlagMaskControl,
    "control": Quartz.kCGEventFlagMaskControl, "fn": Quartz.kCGEventFlagMaskSecondaryFn,
}
BLOCKED = frozenset({"cmd+q", "cmd+w", "cmd+delete", "cmd+backspace", "cmd+opt+escape",
                     "cmd+option+escape", "cmd+shift+q", "cmd+opt+q"})
ESC_KEYCODE = 53

_SOURCE = None
last_escape_post = 0.0


def _source():
    global _SOURCE
    if _SOURCE is None:
        _SOURCE = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStatePrivate)
    return _SOURCE


_MOD_ORDER = {"cmd": 0, "ctrl": 1, "opt": 2, "shift": 3, "fn": 4}
_MOD_ALIAS = {"command": "cmd", "mod": "cmd", "option": "opt", "alt": "opt", "control": "ctrl"}
_KEY_ALIAS = {"esc": "escape", "enter": "return", "backspace": "delete"}


def canonical(hotkey: str) -> str:
    """'Shift+Cmd+T' → 'cmd+shift+t', so equal shortcuts compare equal."""
    parts = [p.strip().lower() for p in hotkey.replace(" ", "").split("+") if p.strip()]
    if not parts:
        return ""
    mods = sorted({_MOD_ALIAS.get(p, p) for p in parts[:-1]}, key=lambda m: _MOD_ORDER.get(m, 9))
    return "+".join(mods + [_KEY_ALIAS.get(parts[-1], parts[-1])])


def parse(hotkey: str) -> tuple[int, int]:
    parts = [p.strip().lower() for p in hotkey.replace(" ", "").split("+") if p.strip()]
    if not parts:
        raise PlanInvalid(f"empty hotkey {hotkey!r}")
    key = parts[-1]
    if key not in KEYCODES:
        raise PlanInvalid(f"unknown key {key!r} in {hotkey!r}")
    flags = 0
    for m in parts[:-1]:
        if m not in MODIFIERS:
            raise PlanInvalid(f"unknown modifier {m!r} in {hotkey!r}")
        flags |= MODIFIERS[m]
    return KEYCODES[key], flags


def is_blocked(hotkey: str) -> bool:
    try:
        return canonical(hotkey) in {canonical(b) for b in BLOCKED}
    except (ValueError, PlanInvalid):
        return False


def post_key(code: int, flags: int = 0) -> None:
    global last_escape_post
    src = _source()
    for down in (True, False):
        ev = Quartz.CGEventCreateKeyboardEvent(src, code, down)
        Quartz.CGEventSetFlags(ev, flags)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    if code == ESC_KEYCODE:
        last_escape_post = time.monotonic()


def press(hotkey: str, pid: int) -> None:
    code, flags = parse(hotkey)
    focus.guard(pid)
    post_key(code, flags)


def type_unicode(text: str, pid: int, chunk: int = 20) -> None:
    """Fallback when paste is blocked: Unicode key events, ≤ 20 UTF-16 units each."""
    focus.guard(pid)
    src = _source()
    buf: list[str] = []
    units = 0
    for ch in text + "\0":
        n = len(ch.encode("utf-16-le")) // 2
        if ch == "\0" or units + n > chunk:
            if buf:
                s = "".join(buf)
                cnt = len(s.encode("utf-16-le")) // 2
                for down in (True, False):
                    ev = Quartz.CGEventCreateKeyboardEvent(src, 0, down)
                    Quartz.CGEventSetFlags(ev, 0)
                    Quartz.CGEventKeyboardSetUnicodeString(ev, cnt, s)
                    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
                time.sleep(0.002)
            buf, units = [], 0
        if ch != "\0":
            buf.append(ch)
            units += n


def escape_pressed() -> bool:
    """The physical Esc key (kill switch). Our own Esc posts pause this for 200 ms."""
    if time.monotonic() - last_escape_post < 0.2:
        return False
    return bool(Quartz.CGEventSourceKeyState(Quartz.kCGEventSourceStateHIDSystemState, ESC_KEYCODE))
