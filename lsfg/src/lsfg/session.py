"""Session: the shared state of one lsfg process, and the observe pipeline.

Holds the alias table, the app index, per-app profiles, menu indexes, the last snapshot per
app, plan bindings (@chosen, {answer}), counters, and the cancel flag. observe() runs the
readiness ladder around the walker: pick window → walk → busy? activate once → frontier?
continue → tiny after launch? poll → verdict.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from .ax import classify, raw, ready, walker, windows
from .ax import menu as menus
from .ax.identity import AliasTable
from .act import apps, focus, keys
from .config import Config
from .errors import AppNotFound, BudgetExceeded, Cancelled, PermissionMissing, ScreenLocked
from .types import AppEntry, Snapshot


@dataclass
class AppCtx:
    entry: AppEntry
    framework: str
    stack: str
    pid: int | None = None
    launched_at: float | None = None

    @property
    def name(self) -> str:
        return self.entry.name

    @property
    def bundle_id(self) -> str:
        return self.entry.bundle_id


@dataclass
class Counters:
    started: float = field(default_factory=time.monotonic)
    steps: int = 0
    opus_calls: int = 0
    jev_calls: int = 0
    tokens: dict = field(default_factory=lambda: {"opus_in": 0, "opus_cached": 0, "opus_out": 0, "jev_in": 0})
    cost_usd: float = 0.0


class NullTracer:
    path = ""

    def event(self, kind: str, **fields: Any) -> None:
        pass

    def close(self) -> None:
        pass


class Session:
    def __init__(self, cfg: Config, tracer=None, profiles=None) -> None:
        self.cfg = cfg
        self.aliases = AliasTable()
        self.apps = apps.AppIndex()
        self.tracer = tracer or NullTracer()
        self.profiles = profiles                       # memory.profiles.Profiles or None
        self.menus: dict[tuple[str, str], list[menus.MenuItem]] = {}
        self.last: dict[int, Snapshot] = {}
        self.bindings: dict[str, Any] = {}
        self.counters = Counters()
        self.cancel = threading.Event()
        self._manual_ax: set[int] = set()
        self._ctx_cache: dict[str, AppCtx] = {}

    # ---------------------------------------------------------------- budgets / cancel
    def check(self) -> None:
        if self.cancel.is_set() or keys.escape_pressed():
            self.cancel.set()
            raise Cancelled("cancelled by the user")
        b = self.cfg.budgets
        if time.monotonic() - self.counters.started > b.task_s:
            raise BudgetExceeded(f"task took longer than {b.task_s:.0f}s")

    def new_task(self) -> None:
        self.counters = Counters()
        self.bindings.clear()
        self.cancel.clear()

    # ---------------------------------------------------------------- apps
    def ctx(self, name: str) -> AppCtx:
        key = name.strip().lower()
        cached = self._ctx_cache.get(key)
        if cached is not None:
            self._refresh_pid(cached)
            return cached
        entry = self.apps.by_bundle(name) if "." in name and " " not in name else None
        entry = entry or self.apps.resolve(name)
        if entry is None:
            raise AppNotFound(f"no installed app matches {name!r}")
        if self.profiles is not None:
            self.profiles.get(entry.bundle_id, entry.version or entry.build)   # relearn on a new version
        fw = classify.bundle_framework(entry.path, entry.bundle_id)
        from .plan.cards import seed_for
        seed_fw = seed_for(entry.bundle_id).get("framework")
        if fw == "appkit" and seed_fw in ("catalyst", "iwork", "custom_cpp", "swiftui", "qt"):
            fw = seed_fw                                          # the codex measured it
        ctx = AppCtx(entry=entry, framework=fw, stack=classify.stack_for(fw))
        if self.profile(entry.bundle_id).get("opaque"):
            ctx.stack = "opaque"
        self._refresh_pid(ctx)
        self._ctx_cache[key] = ctx
        return ctx

    def _refresh_pid(self, ctx: AppCtx) -> None:
        run = apps.running_app(ctx.bundle_id)
        new_pid = int(run.processIdentifier()) if run is not None else None
        if ctx.pid is not None and new_pid != ctx.pid:
            self.aliases.forget_pid(ctx.pid)
            raw.forget_app(ctx.pid)
            self.last.pop(ctx.pid, None)
        ctx.pid = new_pid

    def ensure_running(self, ctx: AppCtx, launch: bool = True, timeout: float | None = None) -> int:
        self._refresh_pid(ctx)
        if ctx.pid is not None:
            return ctx.pid
        if not launch:
            raise AppNotFound(f"{ctx.name} is not running")
        ctx.pid = apps.open_app(ctx.entry, timeout or self.cfg.budgets.open_app_timeout_s)
        ctx.launched_at = time.time()
        return ctx.pid

    def profile(self, bundle_id: str) -> dict:
        if self.profiles is None:
            return {}
        return self.profiles.get(bundle_id)

    def update_profile(self, bundle_id: str, **values: Any) -> None:
        if self.profiles is not None:
            self.profiles.update(bundle_id, **values)

    def menu_items(self, ctx: AppCtx, refresh: bool = False) -> list[menus.MenuItem]:
        key = (ctx.bundle_id, ctx.entry.version)
        if refresh or key not in self.menus:
            pid = self.ensure_running(ctx, launch=False)
            self.menus[key] = menus.read_menus(pid)
        return self.menus[key]

    # ---------------------------------------------------------------- observe
    def observe(self, ctx: AppCtx, *, hint_title: str | None = None, deep: bool = False,
                root_ref: Any = None) -> Snapshot:
        snap = self._observe_once(ctx, hint_title, deep, root_ref)
        if (snap.readiness == "UNTRUSTED" and root_ref is None and ctx.launched_at
                and time.time() - ctx.launched_at < 5):
            deadline = time.monotonic() + 3.0                     # R3: launch transient (LAW-LIFE-11)
            while time.monotonic() < deadline and snap.readiness == "UNTRUSTED":
                self.check()
                time.sleep(0.15)
                snap = self._observe_once(ctx, hint_title, deep, None)
        return snap

    def _observe_once(self, ctx: AppCtx, hint_title: str | None, deep: bool, root_ref: Any) -> Snapshot:
        if screen_locked():
            raise ScreenLocked("the screen is locked (loginwindow is frontmost); unlock the Mac and retry")
        if not raw.trusted():
            raise PermissionMissing("Accessibility permission is missing for the host app "
                                    "(System Settings > Privacy & Security > Accessibility)")
        pid = self.ensure_running(ctx, launch=False)
        raw.STATS.reset()
        t0 = time.perf_counter()
        if ctx.framework in ("electron", "cef", "chromium_browser") and pid not in self._manual_ax:
            app_el = raw.app_element(pid)
            err, ok = raw.settable(app_el, "AXManualAccessibility")
            if err == raw.OK and ok:
                raw.set_attr(app_el, "AXManualAccessibility", True)
            self._manual_ax.add(pid)

        win = None
        kind = "window"
        if root_ref is None:
            win = windows.pick_window(pid, hint_title)
            if win is None:
                for m in windows.minimized_windows(pid):          # un-minimize, then pick again
                    raw.set_attr(m.ref, "AXMinimized", False)
                win = windows.pick_window(pid, hint_title)
            if win is not None:
                windows.attach_cg(win, pid)
                root_ref = win.ref
                if win.sheets:
                    root_ref, kind = win.sheets[0], "sheet"      # a modal blocks the window behind it
            else:
                root_ref, kind = raw.app_element(pid), "app"

        snap = self._walk(ctx, pid, root_ref, kind, win, deep)
        if "app_busy" in snap.truncated:                          # R1: suspended in another Space?
            focus.activate(pid)
            snap = self._walk(ctx, pid, root_ref, kind, win, deep)
        if snap.frontier:                                         # R4: continue, never re-walk the top
            walker.continue_walk(snap, self.aliases, self._budget(ctx, deep))
        walker.post_pass(snap)
        snap.readiness = ready.assess(snap) if kind != "app" else "UNTRUSTED"
        if snap.readiness == "OPAQUE":
            ctx.stack = "opaque"
            self.update_profile(ctx.bundle_id, opaque=True)
        calls = raw.STATS.calls
        if calls >= 20:
            per_call_us = raw.STATS.seconds / calls * 1e6
            if per_call_us > 400 and ctx.stack == "native":
                self.update_profile(ctx.bundle_id, slow_ax=True)
        snap.ax_calls = calls
        snap.timings_ms["total"] = round((time.perf_counter() - t0) * 1000)
        snap.captured_at = time.time()
        self.last[pid] = snap
        self.tracer.event("observe", app=ctx.name, stack=ctx.stack, framework=ctx.framework,
                          readiness=snap.readiness, nodes=len(snap.nodes), frontier=len(snap.frontier),
                          truncated=sorted(snap.truncated), ax_calls=calls, timings_ms=snap.timings_ms,
                          window=snap.window_title if self.cfg.trace.store_ui_text else "")
        return snap

    def _budget(self, ctx: AppCtx, deep: bool) -> walker.Budget:
        b = walker.budget_for(ctx.stack, slow_ax=bool(self.profile(ctx.bundle_id).get("slow_ax")))
        if deep:
            b.max_nodes *= 2
            b.deadline_ms *= 2
        return b

    def _walk(self, ctx: AppCtx, pid: int, root_ref: Any, kind: str, win, deep: bool) -> Snapshot:
        snap = Snapshot(pid=pid, bundle_id=ctx.bundle_id, app_name=ctx.name, framework=ctx.framework,
                        stack=ctx.stack, root_kind=kind,
                        window_title=win.title if win else "", window_bounds=win.bounds if win else None,
                        cg_window_id=win.cg_id if win else None, on_screen=win.on_screen if win else False)
        skip = frozenset({"AXMenuBar"}) if kind == "app" else frozenset()   # menus come from the menu index
        snap.root_alias = walker.walk(snap, root_ref, self.aliases, self._budget(ctx, deep), skip_ax_roles=skip)
        return snap


def screen_locked() -> bool:
    fm = apps.frontmost()
    return fm is not None and fm[0] == "com.apple.loginwindow"
