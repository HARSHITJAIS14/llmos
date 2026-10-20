"""Activation and the frontmost guard (implementation.md §9.8).

AX actions never activate (native trees work in the background, LAW-LIFE-4). Physical input
(keys, pointer, paste) only happens after this guard confirms the target app is frontmost,
so keystrokes never leak into the terminal running lsfg.

Measured on macOS 26 (2026-09-30, E3 redone as E3b): from lsfg's process in a terminal inside
the IDE, every method works in milliseconds (AXFrontmost 0 ms after the call, NSRunningApplication
3–7 ms, NSWorkspace open 14 ms, `open -b`). The first E3 said "all refused" only because it read
NSWorkspace.frontmostApplication, which never updates in a process with no event loop. The
frontmost reading is now live (apps.front_pid). If activation is ever really refused, we remember
it for a while and callers fall back to background AX actions.
"""
from __future__ import annotations

import subprocess
import time
from typing import Any

import AppKit

from ..errors import FocusLost
from ..ax import raw

_blocked_until = 0.0          # after a full failure, skip the slow methods for a while
BLOCK_MEMORY_S = 120.0


def frontmost_pid() -> int | None:
    from .apps import front_pid
    return front_pid()


def focused_app_pid() -> int | None:
    err, ref = raw.attr(raw.system_wide(), "AXFocusedApplication")
    return raw.pid_of(ref) if raw.is_ref(ref) else None


def wait_frontmost(pid: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        if frontmost_pid() == pid:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.01)


def activation_blocked() -> bool:
    return time.monotonic() < _blocked_until


def activate(pid: int, window_ref: Any = None, timeout: float = 0.4) -> bool:
    global _blocked_until
    if raw.is_ref(window_ref):
        raw.perform(window_ref, "AXRaise")                    # raising a window works in the background
        raw.set_attr(window_ref, "AXMain", True)
    if frontmost_pid() == pid:
        return True
    raw.set_attr(raw.app_element(pid), "AXFrontmost", True)
    if wait_frontmost(pid, timeout):
        return True
    from .apps import sync
    sync()
    running = AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
    if running is None:
        return False
    running.activateWithOptions_(AppKit.NSApplicationActivateAllWindows)
    if wait_frontmost(pid, timeout):
        return True
    if activation_blocked():
        return False
    bid = str(running.bundleIdentifier() or "")
    if bid:
        subprocess.run(["osascript", "-e", f'tell application id "{bid}" to activate'],
                       capture_output=True, timeout=5)
        if wait_frontmost(pid, 1.0):
            return True
    _blocked_until = time.monotonic() + BLOCK_MEMORY_S
    return False


def guard(pid: int, tries: int = 1) -> None:
    """Raise FocusLost unless `pid` is frontmost (checked two ways)."""
    for _ in range(tries + 1):
        if frontmost_pid() == pid and focused_app_pid() in (pid, None):
            return
        if not activate(pid):
            break
    raise FocusLost("macOS would not bring the app to the front from this terminal (cooperative activation). "
                    "Accessibility actions still work; keys, pointer clicks and paste need the app in front. "
                    "Click the app once, or run lsfg from Terminal.", frontmost=frontmost_pid())
