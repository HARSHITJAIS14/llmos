"""Typed postconditions — the verification primitives.

The old harness ended tasks with `success = matched is not None or folder_name
in str(s4)`: a substring scan over the whole serialized tree that reports
success when the open failed (the path is still sitting in the file picker's
own text field). These primitives replace that pattern.

Rules:
  * never `x in str(tree)` — always resolve a scope, read a property, compare
  * a postcondition is data (JSON-serializable), so hooks can enforce what
    task scripts declare
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any

from . import axdiff

KINDS = (
    "node_exists",      # a node matching `expect` selectors is present in scope
    "node_absent",      # no node matching `expect` is present in scope
    "value_equals",     # matched node's `value` == expect["value"]
    "value_contains",   # expect["value"] is a substring of matched node's value
    "title_matches",    # a window title in scope matches expect["pattern"] (regex)
)

# Selector fields usable inside `expect`.
_SELECTOR_FIELDS = ("role", "name", "name_contains", "native_id", "value_of")


@dataclass
class Postcondition:
    kind: str
    expect: dict = field(default_factory=dict)
    scope: str = ""             # structural-path prefix; "" = whole tree
    app: str | None = None      # which app to snapshot when evaluated live
    timeout_ms: int = 3000
    description: str = ""

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown postcondition kind {self.kind!r}; valid: {KINDS}")

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str | dict) -> "Postcondition":
        data = json.loads(raw) if isinstance(raw, str) else dict(raw)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Verdict:
    ok: bool
    detail: str
    matched_path: str | None = None

    def __bool__(self) -> bool:
        return self.ok


def _node_matches(attrs: dict, expect: dict) -> bool:
    for key, want in expect.items():
        if key not in _SELECTOR_FIELDS:
            continue
        if key == "name_contains":
            if str(want).lower() not in str(attrs.get("name", "")).lower():
                return False
        elif key == "native_id":
            got = attrs.get("native_id")
            if isinstance(got, dict):
                got = got.get("value")
            if got != want:
                return False
        elif key == "value_of":
            continue  # handled by value_* kinds
        else:
            if attrs.get(key) != want:
                return False
    return True


def _find(content: dict[str, dict], expect: dict, scope: str) -> list[tuple[str, dict]]:
    hits = []
    for path, attrs in content.items():
        if scope and not path.startswith(scope):
            continue
        if _node_matches(attrs, expect):
            hits.append((path, attrs))
    return hits


def evaluate(pc: Postcondition, tree: Any) -> Verdict:
    """Evaluate a postcondition against an already-captured tree state."""
    content, _ = axdiff.flatten(tree)
    hits = _find(content, pc.expect, pc.scope)

    if pc.kind == "node_exists":
        if hits:
            return Verdict(True, f"matched {len(hits)} node(s)", hits[0][0])
        return Verdict(False, f"no node matching {pc.expect} in scope {pc.scope!r}")

    if pc.kind == "node_absent":
        if hits:
            return Verdict(False, f"{len(hits)} node(s) still match {pc.expect}", hits[0][0])
        return Verdict(True, "no matching node present")

    if pc.kind in ("value_equals", "value_contains"):
        want = pc.expect.get("value", "")
        if not hits:
            return Verdict(False, f"no node matching {pc.expect} to read value from")
        for path, attrs in hits:
            got = str(attrs.get("value", ""))
            if pc.kind == "value_equals" and got == str(want):
                return Verdict(True, f"value == {want!r}", path)
            if pc.kind == "value_contains" and str(want) in got:
                return Verdict(True, f"value contains {want!r}", path)
        return Verdict(
            False,
            f"value mismatch: wanted {want!r}, got {str(hits[0][1].get('value', ''))!r}",
            hits[0][0],
        )

    if pc.kind == "title_matches":
        # Accept the aliases models actually write; a literal title is treated
        # as a substring, and an empty expectation is an error, never a pass.
        pattern = pc.expect.get("pattern") or ""
        literal = pc.expect.get("title") or pc.expect.get("name") or ""
        if not pattern and literal:
            pattern = re.escape(str(literal))
        if not pattern:
            return Verdict(False, "title_matches needs expect.pattern (or expect.title); "
                                  "an empty pattern would match everything")
        rx = re.compile(pattern, re.IGNORECASE)
        for path, attrs in content.items():
            if pc.scope and not path.startswith(pc.scope):
                continue
            if attrs.get("role") == "window" and rx.search(str(attrs.get("name", ""))):
                return Verdict(True, f"window title matches {pattern!r}", path)
        return Verdict(False, f"no window title matching {pattern!r}")

    return Verdict(False, f"unhandled kind {pc.kind}")


def evaluate_live(pc: Postcondition, capture_fn=None) -> Verdict:
    """Evaluate against a fresh capture, polling until timeout_ms.

    capture_fn() -> tree dict; defaults to core.snapshot.capture(pc.app).
    """
    import time

    if capture_fn is None:
        from . import snapshot as _snap

        if pc.kind == "title_matches" and not pc.scope:
            # Fast path: window titles come from list-windows in milliseconds;
            # a full DOM snapshot (huge for browsers) proves nothing more.
            def capture_fn():
                return {
                    "role": "application",
                    "children": [
                        {"role": "window", "name": w.get("title", "")}
                        for w in _snap.list_windows(pc.app)
                    ],
                }
        else:
            capture_fn = lambda: _snap.capture(app=pc.app)

    deadline = time.monotonic() + pc.timeout_ms / 1000.0
    last = Verdict(False, "no capture attempted")
    while True:
        try:
            last = evaluate(pc, capture_fn())
        except Exception as exc:  # capture failure is a verdict, not a crash
            last = Verdict(False, f"capture failed: {exc}")
        if last.ok or time.monotonic() >= deadline:
            return last
        time.sleep(0.3)
