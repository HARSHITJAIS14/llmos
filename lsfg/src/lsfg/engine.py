"""The engine: route → plan → execute → verify → learn (implementation.md §15).

One task at a time. Each step: pre-checks → (irreversible gate) → act → wait for post-checks.
A failed step walks the recovery ladder: the other actuation mode → a deeper look (inside
resolve_wait) → JEV choose → JEV explore → Opus replan → ask/fail. Irreversible steps are
never retried automatically: a "failed" Send might have sent.
"""
from __future__ import annotations

import re
import sys
import threading
import time
from typing import Any, Callable

from . import config, router
from .act import apps, clipboard, focus, keys, pointer, semantic
from .ax import caps, classify, raw, windows
from .ax.labels import label
from .ax.normalize import fold
from .errors import (ActionFailed, AppNotFound, BudgetExceeded, Cancelled, CheckFailed, FocusLost, LsfgError,
                     ModelUnavailable, PlanInvalid, SafetyBlocked, ScreenLocked, TargetAmbiguous, TargetNotFound,
                     UserAborted)
from .plan.schema import OPS, SELF_VERIFYING
from .plan.validate import substitute, validate_plan
from .resolve import resolver
from .resolve.selector import SelectorError, fmt, from_node, parse
from .safety import approval, killswitch, policy
from .session import AppCtx, Session, screen_locked
from .trace.trace import Tracer, prune
from .types import Check, Node, Plan, Snapshot, Step, StepResult, TaskResult
from .verify.evaluate import wait_checks
from .vision.ocr import OCR

_LOCK = threading.Lock()                      # one desktop, one task at a time
PRE_CHECK_TIMEOUT = 1.5


class Engine:
    def __init__(self, cfg: config.Config | None = None, *, out: Callable[[str], None] | None = None,
                 interactive: bool | None = None, planner=None, jev=None, memory=None,
                 prompt: Callable[[str], str] | None = None, dialog: bool = True) -> None:
        self.cfg = cfg or config.load_config()
        config.ensure_dirs()
        self.memory = memory
        self.session = Session(self.cfg, profiles=memory.profiles if memory else None)
        self.session.ocr = OCR()
        self.out = out or (lambda s: print(s, flush=True))
        self.interactive = sys.stdin.isatty() if interactive is None else interactive
        self.prompt = prompt or input
        self.dialog = dialog
        self._planner = planner
        self._jev = jev

    # ------------------------------------------------------------------ models (lazy)
    @property
    def planner(self):
        if self._planner is None and self.cfg.anthropic_api_key:
            from .plan.planner import Planner
            self._planner = Planner(self.cfg, self.session)
        return self._planner

    @property
    def jev(self):
        if self._jev is None and self.cfg.typesafe_api_key:
            from .decide.jev import JevClient
            self._jev = JevClient(self.cfg)
        return self._jev

    # ------------------------------------------------------------------ entry point
    def run(self, task: str, *, dry_run: bool = False, yes: bool = False, learn: bool = True,
            plan: Plan | None = None) -> TaskResult:
        if not _LOCK.acquire(blocking=False):
            return TaskResult(status="FAILED", task=task, reason="another task is running")
        s = self.session
        s.new_task()
        s.bindings["task"] = task
        s.tracer = Tracer(task, self.cfg.trace.store_ui_text)
        killswitch.install(s)
        t0 = time.monotonic()
        result = TaskResult(status="FAILED", task=task, trace_path=s.tracer.path)
        slots: dict[str, str] = {}
        try:
            if plan is None:
                plan, slots = self._make_plan(task, result)
            else:
                plan.source = plan.source or "file"
            result.source = plan.source
            self._validate(plan, require_goal=not plan.source.startswith(("intent:", "route:")))
            s.tracer.event("plan", source=plan.source, plan=plan.to_json())
            if dry_run:
                self._print_plan(plan)
                result.status = "DRY_RUN"
            else:
                ok = self._execute(plan, result, yes=yes, task=task)
                result.status = "SUCCESS" if ok else (result.status if result.status != "FAILED" else "FAILED")
        except Cancelled as e:
            result.status, result.reason = "CANCELLED", e.message
        except KeyboardInterrupt:
            result.status, result.reason = "CANCELLED", "interrupted"
        except BudgetExceeded as e:
            result.status, result.reason = "BUDGET", e.message
        except ScreenLocked as e:
            result.status, result.reason = "NEEDS_USER", e.message
        except (SafetyBlocked, UserAborted) as e:
            result.status, result.reason = "BLOCKED_BY_SAFETY", e.message
        except (PlanInvalid, ModelUnavailable, AppNotFound) as e:
            result.status, result.reason = "FAILED", f"{e.kind}: {e.message}"
        except LsfgError as e:
            result.status, result.reason = "FAILED", f"{e.kind}: {e.message}"
        finally:
            c = s.counters
            result.total_ms = round((time.monotonic() - t0) * 1000)
            result.opus_calls, result.jev_calls = c.opus_calls, c.jev_calls
            result.tokens, result.cost_usd = dict(c.tokens), round(c.cost_usd, 5)
            if learn and result.status == "SUCCESS" and self.memory is not None and not result.source.startswith("intent:"):
                try:
                    self.memory.learn(task, plan, result, s, slots)
                except Exception as e:                           # learning must never break a task
                    s.tracer.event("learn_error", error=repr(e))
            elif self.memory is not None and result.route_id is not None and result.status != "SUCCESS":
                self.memory.routes.record(result.route_id, ok=False, ms=result.total_ms)
            s.tracer.event("task_end", status=result.status, reason=result.reason, total_ms=result.total_ms,
                           opus_calls=result.opus_calls, jev_calls=result.jev_calls, tokens=result.tokens,
                           cost_usd=result.cost_usd, source=result.source)
            s.tracer.close()
            prune(self.cfg.trace.keep_runs)
            _LOCK.release()
        return result

    def _make_plan(self, task: str, result: TaskResult) -> tuple[Plan, dict]:
        s = self.session
        t = time.perf_counter()
        plan = router.route(task, s)
        if plan is not None:
            s.tracer.event("router", intent=plan.source, ms=round((time.perf_counter() - t) * 1000))
            return plan, {}
        if self.memory is not None:
            hit = self.memory.routes.match(task, s)
            if hit is not None:
                route_id, plan, slots = hit
                result.route_id = route_id
                s.tracer.event("router", route=route_id, slots=slots, ms=round((time.perf_counter() - t) * 1000))
                self.out(f"  route r{route_id} ({self.memory.routes.status_line(route_id)})")
                return plan, slots
        if self.planner is None:
            raise ModelUnavailable("no built-in intent or learned route matches, and ANTHROPIC_API_KEY is not "
                                   "set for the planner (put it in ~/.lsfg/.env)")
        routes = self.memory.routes.for_task(task, s) if self.memory is not None else []
        plan = self.planner.plan(task, routes=routes)
        return plan, {}

    def _validate(self, plan: Plan, require_goal: bool = True) -> None:
        errs = validate_plan(plan, self.session, allowed_schemes=self.cfg.urls.allowed_schemes)
        if not require_goal:
            errs = [e for e in errs if "post check that proves the goal" not in e]
        if errs:
            raise PlanInvalid("; ".join(errs[:6]), errors=errs)

    # ------------------------------------------------------------------ execution
    def _execute(self, plan: Plan, result: TaskResult, *, yes: bool, task: str) -> bool:
        steps = list(plan.steps)
        i = 0
        while i < len(steps):
            step = steps[i]
            step.index = i
            if step.op == "route":
                steps[i:i + 1] = self._expand_route(step)
                continue
            sr = self._run_step(step, yes=yes)
            result.steps.append(sr)
            self._print_step(step, sr)
            if sr.status in ("PASS", "ASKED"):
                if step.op == "ask":
                    steps = steps[:i + 1] + [substitute(Plan([x]), {"answer": self.session.bindings.get("answer", "")}).steps[0]
                                            for x in steps[i + 1:]]
                i += 1
                continue
            new = self._replan(task, steps, i, sr, result)
            if new is None:
                result.reason = f"step {i} ({step.op}) failed: {sr.error}: {sr.detail}"
                return False
            steps = steps[:i] + new.steps
        self.session.bindings["executed_steps"] = steps
        return True

    def _run_step(self, step: Step, *, yes: bool) -> StepResult:
        s = self.session
        sr = StepResult(index=step.index, op=step.op, status="FAIL")
        t0 = time.perf_counter()
        s.check()
        if screen_locked():
            raise ScreenLocked("the screen is locked (loginwindow is frontmost); unlock the Mac and retry")
        ctx = s.ctx(step.app) if step.app and "app" in OPS[step.op] else None
        irreversible = step.risk == "irreversible" or (ctx is not None and (
            policy.return_in_compose(step, ctx.bundle_id)
            or (step.op == "type" and step.params.get("submit") and policy.submit_sends(ctx.bundle_id))))
        if ctx is not None and policy.denied(ctx.bundle_id, self.cfg.privacy.extra_denylist):
            irreversible = True                                   # denylisted apps: every action is confirmed
        s.bindings["last_press"] = None
        s.tracer.event("step_start", step=step.index, op=step.op, app=step.app, risk=step.risk)
        if ctx is not None and step.op in PHYSICAL_OPS:
            self._reveal_if_hidden(ctx)

        if step.pre:
            ok, res, _ = wait_checks(step.pre, s, PRE_CHECK_TIMEOUT)
            sr.check_results = [r.to_json(self.cfg.trace.store_ui_text) for r in res]
            if not ok:
                bad = next((r for r in res if not r.ok), None)
                sr.error, sr.detail = "CheckFailed", f"pre-check failed: {bad.what if bad else '?'} (saw {bad.observed if bad else '?'})"
                return self._finish(sr, t0)

        post = list(step.post)
        if step.op == "type" and not post and not step.params.get("submit"):
            post = [Check("value", step.app, {"target": step.params["target"], "op": "contains",
                                              "text": step.params["text"]})]
        attempts = {"press": 2, "type": 3, "choose": 2, "menu": 2}.get(step.op, 1)
        timeout = self._step_timeout(step)
        explored = False
        for attempt in range(attempts):
            try:
                s.counters.steps += 1
                if s.counters.steps > self.cfg.budgets.steps:
                    raise BudgetExceeded(f"more than {self.cfg.budgets.steps} actions")
                getattr(self, "_op_" + step.op)(step, ctx, sr, attempt, yes, irreversible)
            except (Cancelled, BudgetExceeded, SafetyBlocked, UserAborted, KeyboardInterrupt):
                raise
            except (TargetNotFound, TargetAmbiguous) as e:
                sr.error, sr.detail = e.kind, e.message
                sr.recovery.append(f"resolve:{e.kind}")
                explored = True
                if not irreversible and not self._no_explore(ctx) and self._explore_fallback(step, ctx, sr, post):
                    return self._finish(sr, t0)
                break
            except LsfgError as e:
                sr.error, sr.detail = e.kind, e.message
                sr.recovery.append(f"{sr.mode or 'act'}:{e.kind}")
                s.tracer.event("act_error", step=step.index, attempt=attempt, error=e.kind, detail=e.message)
                if irreversible:
                    break
                if ctx is not None and "hit-test" in e.message:
                    self._reveal_if_hidden(ctx, force=True)          # the window may have gone off screen
                continue
            if step.op in SELF_VERIFYING and not post:
                sr.status, sr.error, sr.detail = ("ASKED" if step.op == "ask" else "PASS"), None, sr.detail
                break
            ok, res, polls = wait_checks(post, s, timeout)
            sr.check_results = [r.to_json(self.cfg.trace.store_ui_text) for r in res]
            s.tracer.event("wait", step=step.index, polls=polls, ok=ok)
            if ok:
                sr.status, sr.error, sr.detail = "PASS", None, ""
                self._learn_mode(step, ctx, sr, attempt)
                break
            bad = next((r for r in res if not r.ok), None)
            sr.error = "Unverifiable" if bad is not None and bad.unverifiable else "CheckFailed"
            sr.detail = f"{bad.what}: saw {bad.observed!r} {bad.detail}".strip() if bad else "checks failed"
            sr.recovery.append(f"{sr.mode or 'act'}:{sr.error}")
            if irreversible:
                break                                             # never repeat an irreversible action
        if (sr.status == "FAIL" and not explored and not irreversible and sr.error not in ENVIRONMENT_ERRORS
                and step.op in ("press", "type", "choose", "scroll") and not self._no_explore(ctx)):
            if self._explore_fallback(step, ctx, sr, post):
                return self._finish(sr, t0)
        return self._finish(sr, t0)

    @staticmethod
    def _no_explore(ctx: AppCtx | None) -> bool:
        """No improvised clicking in messaging or mail apps: one wrong Return sends, one wrong
        button starts a call."""
        return ctx is not None and policy.submit_sends(ctx.bundle_id)

    def _reveal_if_hidden(self, ctx: AppCtx, force: bool = False) -> None:
        """Clicks and keys need the window on screen. Catalyst apps like WhatsApp keep a hidden
        window when you switch away; activating doesn't show it, a LaunchServices reopen does."""
        s = self.session
        s._refresh_pid(ctx)
        if ctx.pid is None:
            return
        last = s.last.get(ctx.pid)
        hidden = last is not None and last.readiness == "READ_ONLY_HIDDEN"
        if not (hidden or force) or windows.on_screen_window(ctx.pid):
            return
        t0 = time.perf_counter()
        apps.open_app(ctx.entry, timeout=self.cfg.budgets.open_app_timeout_s)
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline and not windows.on_screen_window(ctx.pid):
            time.sleep(0.03)
        s.last.pop(ctx.pid, None)                                # bounds changed: walk again
        s.tracer.event("reveal", app=ctx.name, ms=round((time.perf_counter() - t0) * 1000),
                       on_screen=bool(windows.on_screen_window(ctx.pid)))

    def _finish(self, sr: StepResult, t0: float) -> StepResult:
        sr.timings_ms["total"] = round((time.perf_counter() - t0) * 1000)
        self.session.tracer.event("step_end", step=sr.index, op=sr.op, status=sr.status, error=sr.error,
                                  detail=sr.detail, mode=sr.mode, recovery=sr.recovery, ms=sr.timings_ms["total"],
                                  checks=sr.check_results, resolved=sr.resolved)
        return sr

    def _step_timeout(self, step: Step) -> float:
        b = self.cfg.budgets
        return {"open_app": b.open_app_timeout_s, "open_url": b.open_url_timeout_s,
                "explore": b.explore_timeout_s}.get(step.op, b.step_timeout_s)

    # ------------------------------------------------------------------ targets
    def _target(self, step: Step, ctx: AppCtx, field: str = "target") -> tuple[Node, Snapshot]:
        text = str(step.params.get(field) or "")
        try:
            sel = parse(text)
        except SelectorError as e:
            raise PlanInvalid(str(e))
        self.session.ensure_running(ctx, launch=False)
        res = resolver.resolve_wait(self.session, ctx, sel, self.cfg.budgets.resolve_timeout_s)
        self.session.tracer.event("resolve", step=step.index, selector=text, result=res.kind,
                                  matches=len(res.matches) if res.matches else int(res.found))
        if res.kind == "AMBIGUOUS":
            node = self._disambiguate(res.matches, step, ctx, res.snapshot, text)
            return node, res.snapshot
        if res.kind != "FOUND" or res.node is None:
            raise TargetNotFound(f"{text} not found in {ctx.name}{': ' + res.detail if res.detail else ''}")
        return res.node, res.snapshot

    def _disambiguate(self, matches: list[Node], step: Step, ctx: AppCtx, snap: Snapshot, text: str) -> Node:
        if step.op in ("press", "choose"):
            usable = [m for m in matches if caps.clickable(m, ctx.framework) and caps.actionable(m, ctx.framework)]
            if len(usable) == 1:
                return usable[0]                                  # only one of them can be pressed
        if self.jev is not None and step.risk != "irreversible" and not policy.denied(ctx.bundle_id):
            want = str(step.params.get("want") or f"the element for: {text}")
            node = self.jev.choose(self.session, ctx, snap, matches, want=want, step_goal=f"{step.op} {text}",
                                   irreversible=False)
            if node is not None:
                return node
        labels = [label(n, snap) for n in matches[:3]]
        raise TargetAmbiguous(f"{len(matches)} elements match {text}: {labels}")

    # ------------------------------------------------------------------ ops
    def _op_open_app(self, step: Step, ctx: AppCtx, sr: StepResult, attempt: int, yes: bool, irreversible: bool) -> None:
        s = self.session
        s._refresh_pid(ctx)
        sr.mode = "LAUNCH_SERVICES"
        if ctx.pid is None:
            s.ensure_running(ctx, launch=True)
            return
        if windows.pick_window(ctx.pid) is None:
            apps.open_app(ctx.entry, self.cfg.budgets.open_app_timeout_s)   # reopen: make a window
        focus.activate(ctx.pid)                                             # best effort (E3)

    def _op_open_url(self, step: Step, ctx: AppCtx | None, sr: StepResult, attempt: int, yes: bool, irreversible: bool) -> None:
        url = str(step.params.get("url") or "")
        browser = ctx.entry if ctx is not None else router.default_browser(self.session)
        was_running = ctx is not None and apps.running_app(ctx.bundle_id) is not None
        apps.open_url(url, browser, self.cfg.urls.allowed_schemes)
        sr.mode = "LAUNCH_SERVICES"
        if ctx is not None:
            self.session._refresh_pid(ctx)
            if not was_running:
                ctx.launched_at = time.time()
            if ctx.pid is not None and not focus.activate(ctx.pid):   # best effort (E3)
                sr.detail = "opened; macOS kept another app in front"
                self.out(f"  note: {ctx.name} opened the page but macOS kept the current app in front")

    def _op_activate(self, step, ctx, sr, attempt, yes, irreversible) -> None:
        pid = self.session.ensure_running(ctx, launch=True)
        sr.mode = "ACTIVATE"
        if not focus.activate(pid):
            raise FocusLost(f"could not bring {ctx.name} to the front")

    def _op_quit(self, step, ctx, sr, attempt, yes, irreversible) -> None:
        self._approve(step, ctx, sr, f"quit {ctx.name} (apps still ask about unsaved work)", yes)
        sr.mode = "LAUNCH_SERVICES"
        if not apps.quit_app(ctx.entry):
            raise ActionFailed(f"{ctx.name} refused to quit")
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if apps.running_app(ctx.bundle_id) is None:
                sr.detail = "quit"
                return
            time.sleep(0.05)
        raise ActionFailed(f"{ctx.name} is still running (a save dialog may be open)")

    def _op_menu(self, step, ctx, sr, attempt, yes, irreversible) -> None:
        pid = self.session.ensure_running(ctx, launch=False)
        path = [str(p) for p in step.params.get("path") or []]
        if irreversible or policy.label_looks_irreversible(path[-1] if path else ""):
            self._approve(step, ctx, sr, f"choose the menu item {' > '.join(path)}", yes)
        items = self.session.menu_items(ctx, refresh=attempt > 0)
        ok, why = self._menu_press(pid, path, items)
        sr.mode = "MENU"
        if not ok:
            raise ActionFailed(why)

    @staticmethod
    def _menu_press(pid: int, path: list[str], items) -> tuple[bool, str]:
        from .ax import menu as menus
        return menus.press(pid, path, items)

    def _op_hotkey(self, step, ctx, sr, attempt, yes, irreversible) -> None:
        pid = self.session.ensure_running(ctx, launch=False)
        k = str(step.params.get("keys") or "")
        if irreversible:
            sends = k.strip().lower() in ("return", "enter", "cmd+return", "cmd+enter")
            self._approve(step, ctx, sr, f"press {k}" + (" (this sends it)" if sends else ""), yes,
                          draft=self._focused_text(ctx) or str(self.session.bindings.get("last_typed") or ""))
        sr.mode = "KEYBOARD"
        keys.press(k, pid)

    def _press_modes(self, ctx: AppCtx, snap: Snapshot, node: Node) -> list[str]:
        if ctx.stack == "opaque":
            return ["POINTER"]
        if ctx.stack == "qt" or node.bounds is None:
            return ["SEMANTIC"]
        base = ["POINTER", "SEMANTIC"] if ctx.framework in ("electron", "cef") else ["SEMANTIC", "POINTER"]
        learned = (self.session.profile(ctx.bundle_id).get("press_mode") or {}).get(node.role)
        if learned in base:
            base.remove(learned)
            base.insert(0, learned)
        return base

    def _press_node(self, node: Node, snap: Snapshot, ctx: AppCtx, sr: StepResult, attempt: int, button: str) -> None:
        modes = self._press_modes(ctx, snap, node)
        if attempt >= len(modes):
            raise ActionFailed("no other way left to press this element")
        mode = modes[attempt]
        sr.mode = mode
        pid = ctx.pid
        if mode == "SEMANTIC":
            acts = caps.ensure_actions(node)
            if button == "right":
                err = semantic.perform(node, "AXShowMenu")
            elif button == "double":
                name = "AXOpen" if "AXOpen" in acts else "AXConfirm" if "AXConfirm" in acts else None
                if name is None:
                    raise ActionFailed("no accessibility action for a double click")
                err = semantic.perform(node, name)
            else:
                err = semantic.press(node)
            if err != raw.OK:
                raise ActionFailed(f"accessibility action failed ({err})")
        else:
            win = windows.pick_window(pid)
            pointer.click_node(node, pid, button="right" if button == "right" else "left",
                               count=2 if button == "double" else 1, window_ref=win.ref if win else None)
        self.session.bindings["last_press"] = (ctx.bundle_id, node.role, mode, attempt)

    def _op_press(self, step, ctx, sr, attempt, yes, irreversible) -> None:
        node, snap = self._target(step, ctx)
        text = label(node, snap)
        sr.resolved = {"selector": fmt(from_node(node, snap)), "label": text if self.cfg.trace.store_ui_text else ""}
        if irreversible or policy.label_looks_irreversible(text):
            self._approve(step, ctx, sr, f'press "{text}"', yes,
                          draft=self._focused_text(ctx) or str(self.session.bindings.get("last_typed") or ""))
        self._press_node(node, snap, ctx, sr, attempt, str(step.params.get("button") or "left"))

    def _op_type(self, step, ctx, sr, attempt, yes, irreversible) -> None:
        node, snap = self._target(step, ctx)
        if "secure" in node.states:
            raise SafetyBlocked("lsfg never types into password fields")
        text = str(step.params.get("text") or "")
        mode = str(step.params.get("mode") or "replace")
        submit = bool(step.params.get("submit"))
        sr.resolved = {"selector": fmt(from_node(node, snap)), "label": label(node, snap) if self.cfg.trace.store_ui_text else ""}
        sends = submit and (irreversible or policy.submit_sends(ctx.bundle_id))
        in_web = snap.in_web(node.alias) if node.alias in snap.nodes else False
        stack = classify.node_stack(ctx.framework, in_web)
        methods = ["PASTE", "SET_VALUE", "UNICODE"] if stack == "web" else ["PASTE", "SET_VALUE", "UNICODE"]
        if self.session.profile(ctx.bundle_id).get("type_mode") == "unicode":
            methods = ["UNICODE"] + [m for m in methods if m != "UNICODE"]
        if focus.activation_blocked() and focus.frontmost_pid() != ctx.pid:
            methods = ["SET_VALUE"] + [m for m in methods if m != "SET_VALUE"]   # background first (E3)
        if attempt >= len(methods):
            raise ActionFailed("no other way left to enter text here")
        method = methods[attempt]
        sr.mode = method
        pid = ctx.pid
        if method == "SET_VALUE":
            semantic.focus(node)
            err, cur = raw.attr(node.ref, "AXValue")
            new = text if mode == "replace" else (str(cur or "") + text)
            if raw.set_attr(node.ref, "AXValue", new) != raw.OK:
                raise ActionFailed("the field would not take a value")
            deadline = time.monotonic() + 0.3
            while not _value_has(node, text):
                if time.monotonic() >= deadline:              # some fields (WhatsApp search) ignore AXValue
                    raise ActionFailed("the field ignored the new value")
                time.sleep(0.02)
        else:
            if not focus.activate(pid):
                raise FocusLost(f"could not bring {ctx.name} to the front to type")
            self._focus_field(node, pid)
            if mode == "replace":
                if semantic.select_all(node) != raw.OK:
                    keys.press("cmd+a", pid)
            else:
                semantic.caret_to_end(node)
            if method == "PASTE":
                readable = raw.attr(node.ref, "AXValue")[0] in (raw.OK, raw.NO_VALUE)
                landed = (lambda: _value_has(node, text)) if readable else None
                clipboard.paste_text(text, pid, landed=landed)
            else:
                keys.type_unicode(text, pid)
        self.session.bindings["last_typed"] = text
        if submit:
            deadline = time.monotonic() + 0.8
            while time.monotonic() < deadline and not _value_has(node, text):
                time.sleep(0.02)
            if sends:                                            # typed and read back; now ask
                err, landed = raw.attr(node.ref, "AXValue")
                self._approve(step, ctx, sr, "press Return (this sends it)", yes,
                              draft=landed if isinstance(landed, str) and landed.strip() else text)
            keys.press("return", pid)

    def _focus_field(self, node: Node, pid: int) -> None:
        if _is_focused(node, pid):
            return
        semantic.focus(node)
        deadline = time.monotonic() + 0.3
        while time.monotonic() < deadline:
            if _is_focused(node, pid):
                return
            time.sleep(0.02)
        if node.bounds is not None:
            pointer.click_node(node, pid)

    def _op_choose(self, step, ctx, sr, attempt, yes, irreversible) -> None:
        from .decide.candidates import candidates_for
        s = self.session
        s.ensure_running(ctx, launch=False)
        among = str(step.params.get("among") or "")
        want = str(step.params.get("want") or "")
        then = str(step.params.get("then") or "press")
        try:
            sel = parse(among)
        except SelectorError as e:
            raise PlanInvalid(str(e))
        deadline = time.monotonic() + self.cfg.budgets.resolve_timeout_s
        cands: list[Node] = []
        snap = None
        while True:
            s.check()
            res = resolver.resolve(s, ctx, sel)
            snap = res.snapshot
            pool = res.matches if res.kind == "AMBIGUOUS" else ([res.node] if res.node is not None else [])
            cands = candidates_for(pool, snap, ctx, want)
            if cands or time.monotonic() >= deadline:
                break
            time.sleep(0.05)
        if not cands:
            raise TargetNotFound(f"nothing to choose from in {among}")
        node = _exact_pick(cands, snap, want, s.bindings.get("last_typed"))
        if node is None:
            if self.jev is None:
                raise TargetAmbiguous(f"{len(cands)} candidates and no JEV key to choose between them: "
                                      f"{[label(c, snap) for c in cands[:3]]}")
            node = self.jev.choose(s, ctx, snap, cands, want=want, step_goal=want,
                                   irreversible=irreversible)
            if node is None and snap is not None:
                # `among` is the planner's guess at where the list is. When nothing there fits,
                # look at the whole window once (WhatsApp shows search results in their own panel).
                from .decide.candidates import all_candidates
                have = {c.alias for c in cands}
                wide = [c for c in all_candidates(snap, ctx, want) if c.alias not in have]
                if wide:
                    s.tracer.event("choose_widened", among=among, n=len(wide))
                    node = self.jev.choose(s, ctx, snap, wide, want=want, step_goal=want,
                                           irreversible=irreversible)
            if node is None:
                raise TargetAmbiguous(f"JEV was not confident which of {len(cands)} matches '{want}'")
        s.bindings["chosen"] = node
        sr.resolved = {"selector": fmt(from_node(node, snap)), "label": label(node, snap) if self.cfg.trace.store_ui_text else ""}
        if then != "none":
            if irreversible or policy.label_looks_irreversible(label(node, snap)):
                self._approve(step, ctx, sr, f'press "{label(node, snap)}"', yes)
            self._press_node(node, snap, ctx, sr, attempt, "double" if then == "double" else "left")
        else:
            sr.mode = "CHOOSE"

    def _op_scroll(self, step, ctx, sr, attempt, yes, irreversible) -> None:
        node, snap = self._target(step, ctx)
        direction = str(step.params.get("direction") or "down")
        acts = caps.ensure_actions(node)
        sr.mode = "SEMANTIC"
        if direction == "to":
            if "AXScrollToVisible" in acts and semantic.perform(node, "AXScrollToVisible") == raw.OK:
                return
            direction = "down"
        area = node if node.role in ("scrollarea", "list", "table", "outline", "webarea") else next(
            (a for a in snap.ancestors(node.alias) if a.role in ("scrollarea", "webarea")), node)
        action = {"down": "AXScrollDownByPage", "up": "AXScrollUpByPage", "left": "AXScrollLeftByPage",
                  "right": "AXScrollRightByPage"}[direction]
        if action in caps.ensure_actions(area) and semantic.perform(area, action) == raw.OK:
            return
        if area.bounds is None:
            raise ActionFailed("cannot scroll: no page action and no bounds")
        sr.mode = "POINTER"
        cx, cy = area.center
        dy = {"down": -400, "up": 400}.get(direction, 0)
        dx = {"left": 400, "right": -400}.get(direction, 0)
        pointer.scroll_at(cx, cy, dy=dy, dx=dx)

    def _op_explore(self, step, ctx, sr, attempt, yes, irreversible) -> None:
        if self.jev is None:
            raise ModelUnavailable("explore needs JEV (set TYPESAFE_API_KEY)")
        from .decide.explore import explore
        self.session.ensure_running(ctx, launch=True)
        ok, detail = explore(self, step, ctx, list(step.post), sr)
        sr.mode = "EXPLORE"
        if not ok:
            raise CheckFailed(detail)
        sr.detail = detail

    def _op_ask(self, step, ctx, sr, attempt, yes, irreversible) -> None:
        q = str(step.params.get("question") or "")
        options = [str(o) for o in step.params.get("options") or []]
        if not self.interactive:
            raise SafetyBlocked(f"needs your answer: {q} {options}")
        menu = "\n".join(f"   {i}. {o}" for i, o in enumerate(options, 1))
        raw_answer = self.prompt(f"\n  {q}\n{menu}\n  answer> ").strip()
        answer = options[int(raw_answer) - 1] if raw_answer.isdigit() and 0 < int(raw_answer) <= len(options) else raw_answer
        self.session.bindings["answer"] = answer
        sr.mode, sr.detail = "ASK", answer

    def _op_wait(self, step, ctx, sr, attempt, yes, irreversible) -> None:
        sr.mode = "WAIT"

    # ------------------------------------------------------------------ recovery
    def _explore_fallback(self, step: Step, ctx: AppCtx | None, sr: StepResult, post: list[Check]) -> bool:
        """Rung 4: a bounded JEV loop with the step's intent and its post-checks."""
        if ctx is None or not post or self.jev is None or policy.denied(ctx.bundle_id):
            return False
        if self.session.counters.jev_calls >= self.cfg.budgets.jev_calls:
            return False
        from .decide.explore import explore
        goal = _step_goal(step)
        explore_step = Step(index=step.index, op="explore", app=step.app,
                            params={"goal": goal, "inputs": _inputs_of(step), "max_actions": 6}, post=post)
        ok, detail = explore(self, explore_step, ctx, post, sr)
        sr.recovery.append(f"explore:{'PASS' if ok else 'FAIL'}")
        if ok:
            sr.status, sr.error, sr.detail = "PASS", None, detail
        return ok

    def _replan(self, task: str, steps: list[Step], i: int, sr: StepResult, result: TaskResult) -> Plan | None:
        s = self.session
        if self.planner is None or s.counters.opus_calls >= self.cfg.budgets.opus_calls:
            return None
        if steps[i].risk == "irreversible":
            return None                                       # never improvise around an irreversible step
        if sr.error in ENVIRONMENT_ERRORS:
            s.tracer.event("replan_skipped", error=sr.error)
            return None                                       # a new plan can't fix the Mac
        try:
            new = self.planner.replan(task, steps, i, sr)
            self._validate(new)
        except (PlanInvalid, ModelUnavailable) as e:
            s.tracer.event("replan_failed", error=e.kind, detail=e.message)
            return None
        s.tracer.event("plan", source="replan", plan=new.to_json())
        self.out(f"  ↻ replanned from step {i} ({len(new.steps)} steps)")
        return new

    def _expand_route(self, step: Step) -> list[Step]:
        if self.memory is None:
            raise PlanInvalid("route op used but no route store is loaded")
        slots = {kv["key"]: kv["text"] for kv in step.params.get("slots") or [] if isinstance(kv, dict)}
        plan = self.memory.routes.plan_for(int(str(step.params.get("id")).lstrip("r")), slots)
        if plan is None:
            raise PlanInvalid(f"route {step.params.get('id')} not found")
        return plan.steps

    # ------------------------------------------------------------------ safety
    def _confirmed(self, step: Step) -> bool:
        return self.session.bindings.get("_confirmed_step") == id(step)

    def _approve(self, step: Step, ctx: AppCtx, sr: StepResult, action: str, yes: bool, *, draft: str = "") -> None:
        """Ask right before the irreversible part, showing what will happen (safety/approval.py)."""
        if self._confirmed(step):
            return
        checks = [f"{'✓' if r.get('ok') else '✗'} {r.get('what')}"
                  + (f" (saw {r.get('observed')!r})" if r.get("observed") not in (None, "") else "")
                  for r in (sr.check_results or [])]
        note = "" if (step.pre or step.risk == "irreversible") else "the plan did not mark this irreversible"
        ap = approval.Approval(app=ctx.name, action=action, target=self._recipient_hint(ctx), draft=draft,
                               checks=checks, note=note)
        c = self.cfg.confirm
        auto = c.auto_when_explicit and step.pre and _task_names(self.session, step)
        if c.irreversible and not auto:
            approval.ask(ap, yes=yes, interactive=self.interactive, prompt=self.prompt, dialog=self.dialog)
        self.session.bindings["_confirmed_step"] = id(step)
        self.session.tracer.event("approved", step=step.index, auto=bool(auto or yes),
                                  summary=ap.one_line() if self.cfg.trace.store_ui_text else "")

    def _recipient_hint(self, ctx: AppCtx) -> str:
        """Who it goes to, from what's on screen: the window title and the first content heading."""
        snap = self.session.last.get(ctx.pid) if ctx.pid is not None else None
        if snap is None:
            return ""
        parts = []
        if snap.window_title and fold(snap.window_title) != fold(ctx.name):
            parts.append(snap.window_title)
        heads = [label(n, snap) for n in snap.iter() if n.role == "heading" and label(n, snap)]
        parts += heads[:1]
        return " · ".join(dict.fromkeys(parts))[:120]

    def _focused_text(self, ctx: AppCtx) -> str:
        if ctx.pid is None:
            return ""
        err, ref = raw.attr(raw.app_element(ctx.pid), "AXFocusedUIElement")
        if not raw.is_ref(ref):
            return ""
        err, v = raw.attr(ref, "AXValue")
        return v.strip() if isinstance(v, str) else ""

    def _learn_mode(self, step: Step, ctx: AppCtx | None, sr: StepResult, attempt: int) -> None:
        last = self.session.bindings.get("last_press")
        if ctx is None or not last or step.op not in ("press", "choose"):
            return
        bundle, role, mode, at = last
        if at > 0:                                            # the first mode failed, this one passed
            prof = self.session.profile(bundle)
            modes = dict(prof.get("press_mode") or {})
            modes[role] = mode
            self.session.update_profile(bundle, press_mode=modes)
            self.session.tracer.event("law_event", law="press_mode", app=ctx.name, detail=f"{role} → {mode}")

    # ------------------------------------------------------------------ output
    def _print_step(self, step: Step, sr: StepResult) -> None:
        mark = "✓" if sr.status in ("PASS", "ASKED") else "✗"
        what = _step_summary(step, sr, self.cfg.trace.store_ui_text)
        ms = sr.timings_ms.get("total", 0)
        line = f"{mark} {sr.index} {step.op:<9} {what:<58} {ms:>6} ms"
        if sr.status not in ("PASS", "ASKED"):
            line += f"\n    {sr.error}: {sr.detail}"
        elif sr.mode:
            line += f"  [{sr.mode}]"
        self.out(line)

    def _print_plan(self, plan: Plan) -> None:
        self.out(f"plan ({plan.source}):")
        for s in plan.steps:
            self.out(f"  {s.index} {s.op:<9} {_step_summary(s, None, True)}  risk={s.risk}")
            for c in s.pre:
                self.out(f"      pre  {c.kind} {c.params} g={c.group}")
            for c in s.post:
                self.out(f"      post {c.kind} {c.params} g={c.group}")


# ---------------------------------------------------------------------- helpers

def _value_has(node: Node, text: str) -> bool:
    err, v = raw.attr(node.ref, "AXValue")
    return isinstance(v, str) and fold(text) in fold(v)


def _is_focused(node: Node, pid: int) -> bool:
    err, v = raw.attr(node.ref, "AXFocused")
    if v is True:
        return True
    err, ref = raw.attr(raw.app_element(pid), "AXFocusedUIElement")
    if not raw.is_ref(ref):
        return False
    if raw.cf_equal(ref, node.ref):
        return True
    cur = ref
    for _ in range(4):                                         # focus may sit on an inner element
        err, cur = raw.attr(cur, "AXParent")
        if not raw.is_ref(cur):
            return False
        if raw.cf_equal(cur, node.ref):
            return True
    return False


# Failures that a new plan can't fix: they're about the Mac, not the steps. No Opus replan, no
# explore for these; fail fast and say why (live: 2 replans at $0.05 each couldn't fix FocusLost).
ENVIRONMENT_ERRORS = frozenset({"FocusLost", "AppNotFound", "AppNotResponding", "PermissionMissing", "ScreenLocked"})
PHYSICAL_OPS = frozenset({"press", "type", "choose", "scroll", "hotkey"})


def _exact_pick(cands: list[Node], snap: Snapshot, want: str, typed: str | None) -> Node | None:
    """The deterministic shortcut before JEV: exactly one candidate whose label equals the literal."""
    literals = [m.group(1) for m in re.finditer(r"['\"“‘]([^'\"”’]+)['\"”’]", want)]
    literals += [want]
    if typed:
        literals.append(typed)
    for lit in literals:
        f = fold(lit)
        if not f:
            continue
        hits = [c for c in cands if fold(label(c, snap)) == f]
        if len(hits) == 1:
            return hits[0]
    return None


_ACTION_VERB = re.compile(r"\b(send|post|delete|remove|pay|buy|order|submit|publish|share|transfer|reply|forward)\b", re.I)


def _task_names(session, step: Step) -> bool:
    """auto_when_explicit: the task itself names the action AND every pre-check literal."""
    task = fold(session.bindings.get("task") or "")
    if not _ACTION_VERB.search(task):
        return False
    literals = [str(c.params.get(k) or "") for c in step.pre for k in ("text", "pattern")]
    words = [w for lit in literals for w in re.findall(r"[a-z0-9]{3,}", fold(lit))]
    return bool(words) and all(w in task for w in words)


def _step_goal(step: Step) -> str:
    p = step.params
    if step.op == "press":
        return f"press {p.get('target')}"
    if step.op == "type":
        return f"type the input 'text' into {p.get('target')}" + (" and submit" if p.get("submit") else "")
    if step.op == "choose":
        return f"{p.get('want')} (among {p.get('among')})"
    if step.op == "scroll":
        return f"scroll {p.get('direction')} {p.get('target')}"
    return step.op


def _inputs_of(step: Step) -> list[dict]:
    if step.op == "type":
        return [{"key": "text", "text": str(step.params.get("text") or "")}]
    return []


def _step_summary(step: Step, sr: StepResult | None, store: bool) -> str:
    p = step.params
    if step.op == "open_url":
        return f"{step.app or 'browser'} {p.get('url')}"
    if step.op in ("open_app", "activate", "quit", "wait"):
        return step.app
    if step.op == "menu":
        return f"{step.app} {' > '.join(p.get('path') or [])}"
    if step.op == "hotkey":
        return f"{step.app} {p.get('keys')}"
    if step.op == "type":
        t = str(p.get("text") or "")
        return f"{step.app} {p.get('target')} ← {t[:24]!r}" if store else f"{step.app} {p.get('target')}"
    if step.op == "choose":
        chosen = (sr.resolved or {}).get("label") if sr else ""
        return f"{step.app} {p.get('want')}" + (f" → {chosen!r}" if chosen else "")
    if step.op in ("press", "scroll"):
        lab = (sr.resolved or {}).get("label") if sr else ""
        return f"{step.app} {p.get('target')}" + (f" ({lab!r})" if lab else "")
    if step.op == "explore":
        return f"{step.app} {p.get('goal')}"
    if step.op == "ask":
        return str(p.get("question"))
    return step.app
