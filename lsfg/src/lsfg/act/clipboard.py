"""Paste with full save/restore (implementation.md §9.5).

Save every pasteboard item and type → write our text with transient markers → frontmost
guard → Cmd+V → wait until the value landed → restore, but only if nobody else wrote to
the pasteboard meanwhile. Restoring before the app reads the pasteboard can make it paste
the old content, so the restore waits for the landing check.
"""
from __future__ import annotations

import time
from typing import Callable

import AppKit
import Foundation

from . import focus, keys

TRANSIENT = "org.nspasteboard.TransientType"
CONCEALED = "org.nspasteboard.ConcealedType"
MAX_SAVE_BYTES = 50 * 1024 * 1024
UNVERIFIABLE_WAIT_S = 0.12


def _save(pb) -> list[dict] | None:
    saved: list[dict] = []
    total = 0
    for item in pb.pasteboardItems() or []:
        types = {}
        for t in item.types() or []:
            data = item.dataForType_(t)
            if data is None:
                continue
            total += int(data.length())
            if total > MAX_SAVE_BYTES:
                return None
            types[str(t)] = data
        saved.append(types)
    return saved


def _restore(pb, saved: list[dict]) -> None:
    pb.clearContents()
    items = []
    for types in saved:
        it = AppKit.NSPasteboardItem.alloc().init()
        for t, data in types.items():
            it.setData_forType_(data, t)
        items.append(it)
    if items:
        pb.writeObjects_(items)


def paste_text(text: str, pid: int, landed: Callable[[], bool] | None = None, timeout: float = 0.8) -> bool:
    """Returns True if `landed` confirmed the text arrived (or no check was given)."""
    pb = AppKit.NSPasteboard.generalPasteboard()
    saved = _save(pb)
    item = AppKit.NSPasteboardItem.alloc().init()
    item.setString_forType_(text, AppKit.NSPasteboardTypeString)
    item.setData_forType_(Foundation.NSData.data(), TRANSIENT)
    item.setData_forType_(Foundation.NSData.data(), CONCEALED)
    pb.clearContents()
    pb.writeObjects_([item])
    ours = pb.changeCount()
    ok = True
    try:
        focus.guard(pid)
        keys.post_key(keys.KEYCODES["v"], keys.MODIFIERS["cmd"])
        if landed is None:
            time.sleep(UNVERIFIABLE_WAIT_S)
        else:
            deadline = time.monotonic() + timeout
            ok = False
            while time.monotonic() < deadline:
                if landed():
                    ok = True
                    break
                time.sleep(0.02)
    finally:
        if saved is not None and pb.changeCount() == ours:
            _restore(pb, saved)
    return ok
