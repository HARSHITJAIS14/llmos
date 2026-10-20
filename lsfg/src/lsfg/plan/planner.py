"""The planner: one Opus 5.5 call per new task (implementation.md §13; reasoning.md D15–D17, D41).

Structured outputs (output_config.format) make the JSON grammar-constrained. Effort is the
latency dial: Opus 5.5 always thinks adaptively and `thinking: disabled` is a 400, so we never
send `thinking`. The static system prompt (1 h) and the sorted app cards (5 min) are cached.
"""
from __future__ import annotations

import functools
import json
import re
import time
from datetime import datetime
from pathlib import Path

import AppKit

from ..act import apps as appsmod
from ..ax.normalize import fold
from ..errors import LsfgError, ModelInvalidOutput, ModelUnavailable, PlanInvalid
from ..resolve.selector import SelectorError, parse, from_node
from ..types import Plan, Step, StepResult
from . import cards, digest
from .prompts import REPAIR_PREFIX, REPLAN_SUFFIX, SYSTEM_PROMPT
from .schema import parse_plan, plan_schema
from .validate import validate_plan

HOST_APPS = frozenset({"com.apple.Terminal", "com.googlecode.iterm2", "com.microsoft.VSCode",
                       "com.google.antigravity-ide", "dev.warp.Warp-Stable", "com.mitchellh.ghostty",
                       "com.todesktop.230313mzl4w4u92", "net.kovidgoyal.kitty"})
# $ per token for claude-opus-5-5 (platform pricing, 2026-09-30)
PRICE = {"in": 4e-6, "out": 20e-6, "cache_read": 0.2e-6, "write_5m": 5e-6, "write_1h": 8e-6}
MAX_APPS = 3
# App names that are also plain words ("search the mail", "my notes"): they only count as the app
# in an app-like phrase ("open notes", "in mail", "the mail app").
COMMON_WORD_APPS = frozenset({"mail", "notes", "music", "photos", "books", "maps", "news", "calendar",
                              "reminders", "clock", "weather", "stocks", "home", "contacts", "messages",
                              "preview", "calculator", "dictionary", "podcasts", "tv", "shortcuts",
                              "freeform", "journal", "passwords", "phone", "games", "tips", "chess",
                              "stickies", "terminal", "console", "finder"})
APP_CONTEXT = (r"\b(open|launch|start|quit|close|check|use|using|in|on|into|to|via)\s+(the\s+)?{name}\b"
               r"|\b{name}\s+(app|window|call|meeting|chat|channel|workspace|server|doc|page)\b")


# The current screen matters when the task points at it ("reply to this", "the selected file").
DEICTIC = re.compile(r"\b(this|these|here|current|currently|selected|focused|front)\b")
DOMAIN_IN_TEXT = re.compile(r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|org|net|io|ai|dev|app|co|me|tv|gov|edu|in|uk)\b")


def names_site(folded_task: str) -> bool:
    from ..router import _sites
    return (any(re.search(rf"\b{re.escape(k)}\b", folded_task) for k in _sites())
            or bool(DOMAIN_IN_TEXT.search(folded_task)))


@functools.lru_cache(maxsize=1)
def _dictionary() -> frozenset[str]:
    try:
        return frozenset(w for w in Path("/usr/share/dict/words").read_text().split() if w.islower())
    except OSError:
        return frozenset()


def plain_word(name: str) -> bool:
    """An app called by an everyday word ("Mail", "Space", "Notion") is ambiguous in a task."""
    return name in COMMON_WORD_APPS or (" " not in name and name in _dictionary())


def named_as_app(name: str, folded_task: str, task: str) -> bool:
    """'open notes', 'on slack', 'the zoom call', or a capitalized 'Notion' mid-sentence."""
    if re.search(APP_CONTEXT.replace("{name}", re.escape(name)), folded_task):
        return True
    cap = name[:1].upper() + name[1:]
    for m in re.finditer(rf"\b{re.escape(cap)}\b", task):
        before = task[:m.start()].rstrip()
        if before and before[-1] not in ".!?:":
            return True
    return False


class Planner:
    def __init__(self, cfg, session, client=None) -> None:
        self.cfg = cfg
        self.session = session
        if client is None:
            import anthropic
            client = anthropic.Anthropic(api_key=cfg.anthropic_api_key, max_retries=1,
                                         timeout=cfg.planner.timeout_s)
        self.client = client
        self._digest_aliases: set[str] = set()
        self._digest_snap = None
        self._with_routes = False                                 # the route op is offered only when routes are listed

    # ------------------------------------------------------------------ context
    def _mentioned_apps(self, task: str) -> list:
        t = f" {fold(task)} "
        found = []
        for e in self.session.apps._all():
            for n in {fold(e.name), fold(e.display_name)}:
                if len(n) < 3 or f" {n} " not in t or e.bundle_id in [x.bundle_id for x in found]:
                    continue
                if plain_word(n) and not named_as_app(n, t, task):
                    continue                                      # "the mail from space" is not Mail or Space
                found.append(e)
        for alias, target in self.session.apps.aliases.items():
            if f" {alias} " in t and not (plain_word(alias) and not named_as_app(alias, t, task)):
                e = self.session.apps.resolve(target)
                if e and e.bundle_id not in [x.bundle_id for x in found]:
                    found.append(e)
        found.sort(key=lambda e: t.find(f" {fold(e.name)} ") if f" {fold(e.name)} " in t else 999)
        return found[:MAX_APPS]

    def _contexts(self, task: str, routes: list) -> list:
        s = self.session
        ctxs = []
        for e in self._mentioned_apps(task):
            try:
                ctxs.append(s.ctx(e.bundle_id))
            except LsfgError:
                pass
        # The frontmost app's screen goes in only when the task doesn't name its own target
        # (an app or a site) or points at the screen. Otherwise it's wasted tokens, and it sends
        # whatever the user happens to be looking at.
        t = fold(task)
        wants_front = bool(DEICTIC.search(t)) or (not ctxs and not names_site(t))
        fm = appsmod.frontmost()
        if (fm and wants_front and fm[0] not in HOST_APPS and fm[0] not in [c.bundle_id for c in ctxs]
                and len(ctxs) < MAX_APPS):
            try:
                ctxs.append(s.ctx(fm[0]))
            except LsfgError:
                pass
        for r in routes or []:
            for bid in r.get("bundle_ids", []):
                if bid not in [c.bundle_id for c in ctxs] and len(ctxs) < MAX_APPS:
                    try:
                        ctxs.append(s.ctx(bid))
                    except LsfgError:
                        pass
        return ctxs

    def _screen(self, ctxs: list) -> str:
        from ..safety import policy
        self._digest_aliases, self._digest_snap = set(), None
        for ctx in ctxs:
            self.session._refresh_pid(ctx)
            if ctx.pid is None:
                continue
            try:
                snap = self.session.observe(ctx)
            except LsfgError:
                continue
            text, aliases = digest.build(snap, framework=ctx.framework,
                                         denied=policy.denied(ctx.bundle_id, self.cfg.privacy.extra_denylist),
                                         keep=str(self.session.bindings.get("task") or ""))
            self._digest_aliases, self._digest_snap = aliases, snap
            return text
        if not ctxs:
            return "(not needed: the task names its own target; plan from the task)"
        return f"{', '.join(c.name for c in ctxs)} not running (no screen yet)"

    def _dynamic(self, task: str, ctxs: list, routes: list, screen: str) -> str:
        fm = appsmod.frontmost()
        appsmod.sync()
        running = sorted({str(a.localizedName()) for a in AppKit.NSWorkspace.sharedWorkspace().runningApplications()
                          if a.activationPolicy() == 0})
        now = datetime.now().astimezone()
        from ..router import default_browser, last_used_browser
        last, default = last_used_browser(self.session), default_browser(self.session)
        lines = [f"TASK: {task}",
                 f"NOW: {now.strftime('%Y-%m-%d %H:%M %a')} ({now.tzname()})",
                 f"FRONTMOST: {fm[2] if fm else '-'}",
                 f"RUNNING: {', '.join(running[:30])}",
                 f"BROWSERS: last used {last.name if last else '-'} · default {default.name if default else '-'}"]
        if routes:
            lines.append("ROUTES: " + "; ".join(f"r{r['id']} \"{r['template']}\" ({r['runs']} runs, {r['passes']} pass)"
                                                for r in routes[:10]))
        lines.append("SCREEN: " + screen)
        return "\n".join(lines)

    # ------------------------------------------------------------------ calls
    def _system(self, ctxs: list) -> list[dict]:
        blocks = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral", "ttl": "1h"}}]
        app_cards = "\n\n".join(cards.card_for(self.session, c) for c in sorted(ctxs, key=lambda c: c.bundle_id))
        if app_cards:
            blocks.append({"type": "text", "text": "APP CARDS\n" + app_cards, "cache_control": {"type": "ephemeral"}})
        return blocks

    def _call(self, system: list[dict], user: str, effort: str) -> dict:
        s = self.session
        if s.counters.opus_calls >= self.cfg.budgets.opus_calls:
            raise ModelUnavailable(f"more than {self.cfg.budgets.opus_calls} planner calls for this task")
        kwargs = dict(model=self.cfg.planner.model, max_tokens=self.cfg.planner.max_tokens, system=system,
                      messages=[{"role": "user", "content": user}],
                      output_config={"effort": effort,
                                     "format": {"type": "json_schema",
                                                "schema": plan_schema(self.cfg.planner.schema, self._with_routes)}})
        if self.cfg.planner.fast:
            kwargs["extra_headers"] = {"anthropic-beta": "fast-mode-2026-02-01"}
            kwargs["extra_body"] = {"speed": "fast"}
        t0 = time.perf_counter()
        try:
            resp = self.client.messages.create(**kwargs)
        except Exception as e:                                   # anthropic.APIError and transport errors
            msg = str(e)
            if (getattr(e, "status_code", None) == 400 and "schema" in msg.lower()
                    and self.cfg.planner.schema != "flat"):
                self.cfg.planner.schema = "flat"                   # the API rejected anyOf/const: use the flat form
                self.session.tracer.event("schema_fallback", error=msg[:300])
                return self._call(system, user, effort)
            raise ModelUnavailable(f"planner call failed: {type(e).__name__}: {msg[:200]}") from e
        ms = round((time.perf_counter() - t0) * 1000)
        s.counters.opus_calls += 1
        self._account(resp, ms, effort)
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ModelInvalidOutput(f"planner returned invalid JSON: {e}") from e

    def _account(self, resp, ms: int, effort: str) -> None:
        u = getattr(resp, "usage", None)
        c = self.session.counters
        tin = int(getattr(u, "input_tokens", 0) or 0)
        tout = int(getattr(u, "output_tokens", 0) or 0)
        read = int(getattr(u, "cache_read_input_tokens", 0) or 0)
        write = int(getattr(u, "cache_creation_input_tokens", 0) or 0)
        split = getattr(u, "cache_creation", None)
        w1h = int(getattr(split, "ephemeral_1h_input_tokens", 0) or 0) if split is not None else 0
        w5m = max(0, write - w1h)
        c.tokens["opus_in"] = c.tokens.get("opus_in", 0) + tin + read + write
        c.tokens["opus_cached"] = c.tokens.get("opus_cached", 0) + read
        c.tokens["opus_out"] = c.tokens.get("opus_out", 0) + tout
        c.cost_usd += (tin * PRICE["in"] + tout * PRICE["out"] + read * PRICE["cache_read"]
                       + w5m * PRICE["write_5m"] + w1h * PRICE["write_1h"])
        self.session.tracer.event("opus", ms=ms, effort=effort, input_tokens=tin, cache_read=read,
                                  cache_write=write, output_tokens=tout, model=self.cfg.planner.model)

    # ------------------------------------------------------------------ plan / replan
    def plan(self, task: str, routes: list | None = None) -> Plan:
        self._with_routes = bool(routes)
        ctxs = self._contexts(task, routes or [])
        screen = self._screen(ctxs)
        system = self._system(ctxs)
        user = self._dynamic(task, ctxs, routes or [], screen)
        return self._plan_with_repair(system, user, self.cfg.planner.effort, "planner")

    def replan(self, task: str, steps: list[Step], i: int, sr: StepResult) -> Plan:
        failed = steps[i]
        self._with_routes = False
        ctxs = self._contexts(task + " " + failed.app, [])
        screen = self._screen([c for c in ctxs if c.name == failed.app] + ctxs)
        system = self._system(ctxs)
        done = f"steps 0-{i - 1} passed" if i > 0 else "nothing has run yet"
        user = (self._dynamic(task, ctxs, [], screen)
                + f"\nFAILED: step {i} {failed.op} {json.dumps(failed.params, default=str)[:300]} → {sr.error}: {sr.detail[:300]}"
                + f"\nTRIED: {', '.join(sr.recovery) or 'nothing else'}"
                + f"\nDONE: {done}\n" + REPLAN_SUFFIX)
        return self._plan_with_repair(system, user, self.cfg.planner.replan_effort, "replan")

    def _plan_with_repair(self, system: list[dict], user: str, effort: str, source: str) -> Plan:
        data = self._call(system, user, effort)
        plan, errs = self._check(data, source)
        if errs:
            self.session.tracer.event("plan_invalid", errors=errs[:10])
            data = self._call(system, user + "\n\n" + REPAIR_PREFIX + "\n".join(f"- {e}" for e in errs[:12])
                              + "\nPREVIOUS PLAN:\n" + json.dumps(data)[:6000], "low")
            plan, errs = self._check(data, source)
            if errs:
                raise PlanInvalid("the planner's plan failed validation twice: " + "; ".join(errs[:5]), errors=errs)
        self._bind_aliases(plan)
        return plan

    def _check(self, data: dict, source: str) -> tuple[Plan | None, list[str]]:
        try:
            plan = parse_plan(data, source=source)
        except PlanInvalid as e:
            return None, [e.message]
        errs = validate_plan(plan, self.session, digest_aliases=self._digest_aliases,
                             allowed_schemes=self.cfg.urls.allowed_schemes)
        return plan, errs

    def _bind_aliases(self, plan: Plan) -> None:
        """@eN → stored selector, so a vanished alias still resolves and routes never store aliases."""
        snap = self._digest_snap
        if snap is None:
            return
        table = self.session.bindings.setdefault("alias_selectors", {})
        for s in plan.steps:
            texts = [s.params.get(f) for f in ("target", "among")] + [c.params.get("target") for c in s.pre + s.post]
            for t in texts:
                if isinstance(t, str) and re.fullmatch(r"@e\d+", t):
                    node = snap.nodes.get(t[1:])
                    if node is not None:
                        try:
                            table[t[1:]] = from_node(node, snap)
                        except SelectorError:
                            pass
