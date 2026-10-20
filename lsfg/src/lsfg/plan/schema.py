"""One op table drives the planner's JSON schema, the parser, and the executor (§13.4).

Top level: {"steps": [...], "checks": [...]}. Every field is required (the API allows at most
24 optional parameters) and there are only two unions: step items and check items (at most 16
allowed). Checks live at the top level and point at steps by index ("s").
"""
from __future__ import annotations

from typing import Any

from ..errors import PlanInvalid
from ..types import Plan, Step
from ..verify import checks as checkmod

RISK = ["safe", "irreversible"]

OPS: dict[str, dict[str, Any]] = {
    "open_app": {"app": "string"},
    "open_url": {"app": "string", "url": "string"},
    "activate": {"app": "string"},
    "quit": {"app": "string", "risk": RISK},
    "menu": {"app": "string", "path": "string[]", "risk": RISK},
    "hotkey": {"app": "string", "keys": "string", "risk": RISK},
    "press": {"app": "string", "target": "string", "button": ["left", "double", "right"], "risk": RISK},
    "type": {"app": "string", "target": "string", "text": "string", "mode": ["replace", "append"],
             "submit": "boolean", "risk": RISK},
    "choose": {"app": "string", "among": "string", "want": "string", "then": ["press", "double", "none"],
               "risk": RISK},
    "scroll": {"app": "string", "target": "string", "direction": ["up", "down", "left", "right", "to"]},
    "explore": {"app": "string", "goal": "string", "inputs": "kv[]", "max_actions": "integer"},
    "route": {"id": "string", "slots": "kv[]"},
    "ask": {"question": "string", "options": "string[]"},
    "wait": {"app": "string"},
}

CHECK_FIELDS: dict[str, dict[str, Any]] = {
    "frontmost": {"app": "string"},
    "running": {"app": "string"},
    "title": {"app": "string", "pattern": "string"},
    "url": {"app": "string", "pattern": "string"},
    "exists": {"app": "string", "target": "string"},
    "absent": {"app": "string", "target": "string"},
    "value": {"app": "string", "target": "string", "op": list(checkmod.VALUE_OPS), "text": "string"},
    "state": {"app": "string", "target": "string", "state": list(checkmod.STATES), "is": "boolean"},
    "text": {"app": "string", "text": "string", "region": "string"},
    "menu_checked": {"app": "string", "path": "string[]", "is": "boolean"},
}

SELF_VERIFYING = frozenset({"quit", "ask", "route", "explore"})   # verify inside the op
TARGET_FIELDS = {"press": ("target",), "type": ("target",), "choose": ("among",), "scroll": ("target",)}


def _prop(t: Any) -> dict:
    if isinstance(t, list):
        return {"type": "string", "enum": t}
    if t == "string":
        return {"type": "string"}
    if t == "boolean":
        return {"type": "boolean"}
    if t == "integer":
        return {"type": "integer"}
    if t == "string[]":
        return {"type": "array", "items": {"type": "string"}}
    if t == "kv[]":
        return {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                           "required": ["key", "text"],
                                           "properties": {"key": {"type": "string"}, "text": {"type": "string"}}}}
    raise ValueError(t)


def _ref_prop(t: Any) -> dict:
    """Like _prop, but repeated shapes point at $defs to keep the schema (input tokens) small."""
    if t == RISK:
        return {"$ref": "#/$defs/risk"}
    if t == "kv[]":
        return {"type": "array", "items": {"$ref": "#/$defs/kv"}}
    if t == "string[]":
        return {"$ref": "#/$defs/strs"}
    return _prop(t)


DEFS = {
    "risk": {"type": "string", "enum": RISK},
    "kv": {"type": "object", "additionalProperties": False, "required": ["key", "text"],
           "properties": {"key": {"type": "string"}, "text": {"type": "string"}}},
    "strs": {"type": "array", "items": {"type": "string"}},
    "when": {"type": "string", "enum": ["pre", "post"]},
}


def plan_schema(flavor: str = "anyof", with_routes: bool = True) -> dict:
    if flavor == "flat":
        return _flat_schema(with_routes)
    steps = []
    for op, fields in OPS.items():
        if op == "route" and not with_routes:
            continue
        props = {"op": {"const": op}}
        props.update({f: _ref_prop(t) for f, t in fields.items()})
        steps.append({"type": "object", "properties": props, "required": list(props), "additionalProperties": False})
    checks = []
    for k, fields in CHECK_FIELDS.items():
        props = {"k": {"const": k}, "s": {"type": "integer"}, "when": {"$ref": "#/$defs/when"},
                 "g": {"type": "integer"}}
        props.update({f: _ref_prop(t) for f, t in fields.items()})
        checks.append({"type": "object", "properties": props, "required": list(props), "additionalProperties": False})
    return {"type": "object", "additionalProperties": False, "required": ["steps", "checks"], "$defs": DEFS,
            "properties": {"steps": {"type": "array", "items": {"anyOf": steps}},
                           "checks": {"type": "array", "items": {"anyOf": checks}}}}


def _flat_schema(with_routes: bool = True) -> dict:
    ops = {op: f for op, f in OPS.items() if with_routes or op != "route"}
    step_props: dict[str, dict] = {"op": {"type": "string", "enum": list(ops)}}
    for fields in ops.values():
        for f, t in fields.items():
            step_props.setdefault(f, _prop(t))
    check_props: dict[str, dict] = {"k": {"type": "string", "enum": list(CHECK_FIELDS)},
                                    "s": {"type": "integer"}, "when": {"type": "string", "enum": ["pre", "post"]},
                                    "g": {"type": "integer"}}
    for fields in CHECK_FIELDS.values():
        for f, t in fields.items():
            check_props.setdefault(f, _prop(t))
    obj = lambda props: {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}  # noqa: E731
    return {"type": "object", "additionalProperties": False, "required": ["steps", "checks"],
            "properties": {"steps": {"type": "array", "items": obj(step_props)},
                           "checks": {"type": "array", "items": obj(check_props)}}}


def parse_plan(data: dict, source: str = "planner") -> Plan:
    if not isinstance(data, dict) or not isinstance(data.get("steps"), list):
        raise PlanInvalid("plan must be an object with a 'steps' list")
    steps: list[Step] = []
    for i, s in enumerate(data["steps"]):
        if not isinstance(s, dict):
            raise PlanInvalid(f"step {i} is not an object")
        op = s.get("op")
        if op not in OPS:
            raise PlanInvalid(f"step {i}: unknown op {op!r}")
        fields = OPS[op]
        params = {f: s.get(f) for f in fields if f not in ("app", "risk")}
        step = Step(index=i, op=op, app=str(s.get("app") or ""), params=params,
                    risk=str(s.get("risk") or "safe"))
        for when in ("pre", "post"):                         # inline checks (hand-written plans, routes)
            for c in s.get(when) or []:
                chk = checkmod.from_json({**c, "when": when})
                (step.pre if when == "pre" else step.post).append(chk)
        steps.append(step)
    for c in data.get("checks") or []:
        try:
            si = int(c.get("s", -1))
        except (TypeError, ValueError):
            si = -1
        if not 0 <= si < len(steps):
            raise PlanInvalid(f"check {c.get('k')!r} points at step {c.get('s')!r}, which does not exist")
        chk = checkmod.from_json(c)
        (steps[si].pre if chk.when == "pre" else steps[si].post).append(chk)
    return Plan(steps=steps, source=source)


def plan_to_json(plan: Plan) -> dict:
    """Round-trippable form (inline checks) used for routes and traces."""
    out = []
    for s in plan.steps:
        d = {"op": s.op, "app": s.app, **s.params}
        if "risk" in OPS[s.op]:
            d["risk"] = s.risk
        d["pre"] = [_check_json(c) for c in s.pre]
        d["post"] = [_check_json(c) for c in s.post]
        out.append(d)
    return {"steps": out}


def _check_json(c) -> dict:
    return {"k": c.kind, "app": c.app, **c.params, "g": c.group}
