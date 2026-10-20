"""Apps and URLs through LaunchServices (implementation.md §9.7).

Never Spotlight, never mdfind, never UI search, never osascript. The app index is built from
Info.plist files, so name → app is a dict lookup, and NSWorkspace opens/reopens/activates.
"""
from __future__ import annotations

import ctypes
import json
import os
import plistlib
import threading
import time
from dataclasses import asdict
from importlib import resources
from pathlib import Path

import AppKit
import CoreFoundation as CF
import Foundation

from .. import config
from ..errors import AppNotFound, SafetyBlocked
from ..types import AppEntry
from ..ax.normalize import fold

SCAN_DIRS = [
    "/Applications", "/Applications/Utilities", "/System/Applications",
    "/System/Applications/Utilities", str(Path.home() / "Applications"),
    "/System/Library/CoreServices",
]
_CORE_SERVICES_KEEP = {"Finder", "Screen Sharing", "Ticket Viewer"}
INDEX_TTL_S = 24 * 3600


def _read_entry(app_path: Path) -> AppEntry | None:
    try:
        with open(app_path / "Contents" / "Info.plist", "rb") as f:
            info = plistlib.load(f)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None
    bid = info.get("CFBundleIdentifier")
    if not isinstance(bid, str) or not bid:
        return None
    return AppEntry(
        name=app_path.stem, bundle_id=bid, path=str(app_path),
        version=str(info.get("CFBundleShortVersionString", "") or ""),
        build=str(info.get("CFBundleVersion", "") or ""),
        display_name=str(info.get("CFBundleDisplayName") or info.get("CFBundleName") or app_path.stem),
    )


def _scan() -> list[AppEntry]:
    out: dict[str, AppEntry] = {}
    for d in SCAN_DIRS:
        base = Path(d)
        if not base.is_dir():
            continue
        core = d.endswith("CoreServices")
        try:
            entries = list(os.scandir(base))
        except OSError:
            continue
        for e in entries:
            p = Path(e.path)
            if p.suffix == ".app":
                if core and p.stem not in _CORE_SERVICES_KEEP:
                    continue
                ent = _read_entry(p)
                if ent and ent.path not in out:
                    out[ent.path] = ent
            elif e.is_dir() and not core and not p.name.startswith("."):
                try:
                    for sub in os.scandir(p):
                        sp = Path(sub.path)
                        if sp.suffix == ".app":
                            ent = _read_entry(sp)
                            if ent and ent.path not in out:
                                out[ent.path] = ent
                except OSError:
                    pass
    return list(out.values())


def sync() -> None:
    """Apply pending app-state notifications (7 µs when there are none).

    lsfg runs no event loop (a CLI, a single-threaded daemon), and without one NSWorkspace's
    frontmostApplication and runningApplications, and NSRunningApplication's isFinishedLaunching,
    can keep their first value forever. Measured 2026-09-30 (E3b): Finder was in front, but
    NSWorkspace still said "Antigravity IDE". That stale read was the whole "macOS refuses
    activation" story (E3) and the 15 s "did not finish launching" timeouts.
    """
    try:
        CF.CFRunLoopRunInMode(CF.kCFRunLoopDefaultMode, 0, False)
    except Exception:
        pass


class _PSN(ctypes.Structure):
    _fields_ = [("high", ctypes.c_uint32), ("low", ctypes.c_uint32)]


_live_api: tuple | bool | None = None


def _live():
    """The window server's own front-process call (what the Dock and app switchers read)."""
    global _live_api
    if _live_api is None:
        try:
            sky = ctypes.cdll.LoadLibrary("/System/Library/PrivateFrameworks/SkyLight.framework/SkyLight")
            hi = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
            get_front, get_pid = sky._SLPSGetFrontProcess, hi.GetProcessPID
            get_front.argtypes, get_front.restype = [ctypes.POINTER(_PSN)], ctypes.c_int32
            get_pid.argtypes, get_pid.restype = [ctypes.POINTER(_PSN), ctypes.POINTER(ctypes.c_int)], ctypes.c_int32
            _live_api = (get_front, get_pid)
        except (OSError, AttributeError):
            _live_api = False                                    # gone in some future macOS: use NSWorkspace
    return _live_api


def front_pid() -> int | None:
    """The frontmost app's pid, read live."""
    api = _live()
    if api:
        psn, pid = _PSN(), ctypes.c_int(0)
        if api[0](ctypes.byref(psn)) == 0 and api[1](ctypes.byref(psn), ctypes.byref(pid)) == 0 and pid.value > 0:
            return pid.value
    sync()
    a = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    return int(a.processIdentifier()) if a is not None else None


def _running_entries() -> list[AppEntry]:
    sync()
    out = []
    for a in AppKit.NSWorkspace.sharedWorkspace().runningApplications():
        if a.activationPolicy() != 0:
            continue
        bid = a.bundleIdentifier()
        url = a.bundleURL()
        if not bid or url is None:
            continue
        out.append(AppEntry(name=str(a.localizedName() or ""), bundle_id=str(bid), path=str(url.path()),
                            display_name=str(a.localizedName() or "")))
    return out


def _levenshtein(a: str, b: str, cap: int = 2) -> int:
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _load_aliases() -> dict[str, str]:
    try:
        return json.loads(resources.files("lsfg.data").joinpath("app_aliases.json").read_text())
    except (OSError, ValueError, ModuleNotFoundError):
        return {}


class AppIndex:
    def __init__(self, cache_path: Path | None = None) -> None:
        self.cache_path = cache_path or (config.CACHE_DIR / "apps.json")
        self.entries: list[AppEntry] = []
        self.aliases = {fold(k): v for k, v in _load_aliases().items()}
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.cache_path.read_text())
            if time.time() - float(data.get("built_at", 0)) < INDEX_TTL_S:
                self.entries = [AppEntry(**e) for e in data.get("entries", [])]
                return
        except (OSError, ValueError, TypeError):
            pass
        self.rebuild()

    def rebuild(self) -> None:
        self.entries = _scan()
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(
                {"built_at": time.time(), "entries": [asdict(e) for e in self.entries]}))
        except OSError:
            pass

    def _all(self) -> list[AppEntry]:
        seen = {e.bundle_id for e in self.entries}
        return self.entries + [e for e in _running_entries() if e.bundle_id not in seen]

    def by_bundle(self, bundle_id: str) -> AppEntry | None:
        for e in self._all():
            if e.bundle_id == bundle_id:
                return e
        return None

    def resolve(self, name: str) -> AppEntry | None:
        q = fold(name.removesuffix(".app"))
        if not q:
            return None
        hit = self._resolve_once(q)
        if hit is None:
            self.rebuild()                                  # maybe it was just installed
            hit = self._resolve_once(q)
        return hit

    def _resolve_once(self, q: str) -> AppEntry | None:
        entries = self._all()
        names = [(e, {fold(e.name), fold(e.display_name)}) for e in entries]
        exact = [e for e, ns in names if q in ns]
        if exact:
            return _prefer(exact)
        target = self.aliases.get(q)
        if target:
            t = fold(target)
            ali = [e for e, ns in names if t in ns or e.bundle_id == target]
            if ali:
                return _prefer(ali)
        prefix = [e for e, ns in names if any(n.startswith(q + " ") or n.startswith(q) for n in ns)]
        if len(prefix) == 1:
            return prefix[0]
        if len(q) >= 5:
            close = [e for e, ns in names if any(_levenshtein(q, n) <= 1 for n in ns)]
            if len(close) == 1:
                return close[0]
        return None


def _prefer(entries: list[AppEntry]) -> AppEntry:
    """Several entries with one name (e.g. a CoreServices copy): prefer running, then /Applications."""
    sync()
    running = {str(a.bundleIdentifier()) for a in AppKit.NSWorkspace.sharedWorkspace().runningApplications()}
    return sorted(entries, key=lambda e: (e.bundle_id not in running, not e.path.startswith("/Applications"),
                                          len(e.path)))[0]


def running_app(bundle_id: str):
    sync()
    apps = list(AppKit.NSRunningApplication.runningApplicationsWithBundleIdentifier_(bundle_id) or [])
    apps = [a for a in apps if not a.isTerminated()]
    if not apps:
        return None
    regular = [a for a in apps if a.activationPolicy() == 0]
    return (regular or apps)[0]


def frontmost() -> tuple[str, int, str] | None:
    pid = front_pid()
    a = AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(pid) if pid else None
    if a is None:
        return None
    return (str(a.bundleIdentifier() or ""), int(a.processIdentifier()), str(a.localizedName() or ""))


def _config(activates: bool = True):
    cfg = AppKit.NSWorkspaceOpenConfiguration.configuration()
    cfg.setActivates_(activates)
    return cfg


def open_app(entry: AppEntry, timeout: float = 15.0) -> int:
    """Launch, or activate + reopen (LaunchServices creates a window if none is open). Returns pid."""
    done = threading.Event()
    result: dict = {}

    def handler(app, error):
        result["app"], result["error"] = app, error
        done.set()

    url = Foundation.NSURL.fileURLWithPath_(entry.path)
    AppKit.NSWorkspace.sharedWorkspace().openApplicationAtURL_configuration_completionHandler_(
        url, _config(True), handler)
    done.wait(timeout)
    if result.get("error") is not None and result.get("app") is None:
        raise AppNotFound(f"could not open {entry.name}: {result['error']}")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sync()                                                   # else isFinishedLaunching never changes
        app = result.get("app") or running_app(entry.bundle_id)
        if app is not None and app.isFinishedLaunching():
            return int(app.processIdentifier())
        time.sleep(0.03)
    raise AppNotFound(f"{entry.name} did not finish launching in {timeout:.0f}s")


def check_url(url: str, allowed: list[str]) -> str:
    scheme = url.split(":", 1)[0].lower() if ":" in url else ""
    if scheme not in {s.lower() for s in allowed}:
        raise SafetyBlocked(f"URL scheme {scheme!r} is not allowed", url=url)
    return url


def open_url(url: str, browser: AppEntry | None, allowed: list[str], timeout: float = 5.0) -> None:
    check_url(url, allowed)
    nsurl = Foundation.NSURL.URLWithString_(url)
    if nsurl is None:
        raise SafetyBlocked(f"not a valid URL: {url!r}")
    done = threading.Event()
    result: dict = {}

    def handler(*args):
        result["args"] = args
        done.set()

    ws = AppKit.NSWorkspace.sharedWorkspace()
    if browser is not None:
        app_url = Foundation.NSURL.fileURLWithPath_(browser.path)
        ws.openURLs_withApplicationAtURL_configuration_completionHandler_([nsurl], app_url, _config(True), handler)
    else:
        ws.openURL_configuration_completionHandler_(nsurl, _config(True), handler)
    done.wait(timeout)
    args = result.get("args") or ()
    if len(args) >= 2 and args[1] is not None and args[0] is None:
        raise AppNotFound(f"could not open {url}: {args[1]}")


def quit_app(entry: AppEntry) -> bool:
    app = running_app(entry.bundle_id)
    if app is None:
        return True
    return bool(app.terminate())
