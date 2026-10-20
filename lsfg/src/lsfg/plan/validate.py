"""Plan validation, for every source: intents, routes, files, and the planner (§13.5)."""
from __future__ import annotations

import re

from ..act import apps as appsmod
from ..act import keys
from ..errors import SafetyBlocked
from ..resolve.selector import SelectorError, parse
from ..types import Plan
from ..verify import checks as checkmod
from .schema import OPS, SELF_VERIFYING, TARGET_FIELDS

MAX_STEPS = 12
MAX_EXPLORE = 8


def validate_plan(plan: Plan, session=None, *, digest_aliases: set[str] | None = None,
                  max_steps: int = MAX_STEPS, allowed_schemes: list[str] | None = None) -> list[str]:
    errs: list[str] = []
    if not plan.steps:
        return ["plan has no steps"]
    if len(plan.steps) > max_steps:
        errs.append(f"plan has {len(plan.steps)} steps (max {max_steps})")
    for s in plan.steps:
        where = f"step {s.index} ({s.op})"
        p = s.params
        if s.op not in OPS:
            errs.append(f"{where}: unknown op")
            continue
        needs_app = "app" in OPS[s.op] and not (s.op == "open_url" and not s.app)
        if needs_app and not s.app:
            errs.append(f"{where}: app is required")
        elif needs_app and session is not None and session.apps.resolve(s.app) is None:
            errs.append(f"{where}: no installed app matches {s.app!r}")
        if s.risk not in ("safe", "irreversible"):
            errs.append(f"{where}: risk must be safe or irreversible")
        if s.op == "open_url":
            url = str(p.get("url") or "")
            if not url:
                errs.append(f"{where}: url is required")
            else:
                try:
                    appsmod.check_url(url, allowed_schemes or ["http", "https"])
                except SafetyBlocked as e:
                    errs.append(f"{where}: {e.message}")
        if s.op == "type" and not str(p.get("text") or ""):
            errs.append(f"{where}: text is required")
        if s.op == "menu" and not p.get("path"):
            errs.append(f"{where}: path is required")
        if s.op == "hotkey":
            k = str(p.get("keys") or "")
            try:
                keys.parse(k)
                if keys.is_blocked(k) and s.risk != "irreversible":
                    errs.append(f"{where}: {k} is blocked (it can close or quit things)")
            except Exception as e:                           # PlanInvalid from keys.parse
                errs.append(f"{where}: {e}")
        if s.op == "choose" and not str(p.get("want") or "").strip():
            errs.append(f"{where}: want is required")
        if s.op == "explore":
            if not str(p.get("goal") or "").strip():
                errs.append(f"{where}: goal is required")
            if int(p.get("max_actions") or 0) > MAX_EXPLORE:
                errs.append(f"{where}: max_actions > {MAX_EXPLORE}")
            if s.risk == "irreversible":
                errs.append(f"{where}: explore can never be irreversible")
        if s.op == "ask" and not str(p.get("question") or "").strip():
            errs.append(f"{where}: question is required")
        if s.op == "route" and not str(p.get("id") or "").strip():
            errs.append(f"{where}: route id is required")
        for f in TARGET_FIELDS.get(s.op, ()):
            t = str(p.get(f) or "")
            if not t:
                errs.append(f"{where}: {f} is required")
                continue
            errs += _selector_errors(t, where, digest_aliases)
        for c in s.pre + s.post:
            errs += [f"{where}: {e}" for e in checkmod.validate(c)]
            if "target" in c.params and c.params.get("target"):
                errs += _selector_errors(str(c.params["target"]), where, digest_aliases)
            if c.kind == "text" and c.params.get("region") not in (None, "", "window"):
                errs += _selector_errors(str(c.params["region"]), where, digest_aliases)
        if s.risk == "irreversible" and not any(c.kind not in checkmod.TRIVIAL for c in s.pre):
            errs.append(f"{where}: irreversible step needs a pre check proving the target is right")
    last = plan.steps[-1]
    if last.op not in SELF_VERIFYING and not any(c.kind not in checkmod.TRIVIAL or last.op in ("open_app", "activate")
                                                 for c in last.post):
        errs.append(f"step {last.index} ({last.op}): the last step needs a post check that proves the goal")
    return errs


def _selector_errors(text: str, where: str, aliases: set[str] | None) -> list[str]:
    try:
        sel = parse(text)
    except SelectorError as e:
        return [f"{where}: {e.message}"]
    if sel.special and sel.special.startswith("alias:") and aliases is not None:
        a = sel.special.split(":", 1)[1]
        if a not in aliases:
            return [f"{where}: @{a} is not in the SCREEN digest"]
    return []


def substitute(plan: Plan, values: dict[str, str]) -> Plan:
    """Fill {slot} / {answer} placeholders in every string field and check."""
    if not values:
        return plan
    import urllib.parse
    rx = re.compile(r"\{(\w+)(?::(re|url))?\}")

    def one(m):
        v = values.get(m.group(1))
        if v is None:
            return m.group(0)
        if m.group(2) == "re":
            return re.escape(v)
        if m.group(2) == "url":
            return urllib.parse.quote_plus(v)
        return v

    def fill(v):
        if isinstance(v, str):
            return rx.sub(one, v)
        if isinstance(v, list):
            return [fill(x) for x in v]
        if isinstance(v, dict):
            return {k: fill(x) for k, x in v.items()}
        return v

    for s in plan.steps:
        s.params = fill(s.params)
        for c in s.pre + s.post:
            c.params = fill(c.params)
    return plan
