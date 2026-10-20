"""Identity-keyed accessibility-tree diffs.

The old implementation keyed diff lines by structural path but kept every node
attribute — including `ref_id`, which agent-desktop reassigns on every snapshot
(`:e13` -> `:e119`). Result: ~95% of "changed" lines were ref churn and the diff
was as large as the snapshot it was meant to replace.

Fix: the structural path (role:name + sibling index) IS the node's identity, so
ephemeral attributes are excluded from the diffed content entirely and kept in a
sidecar map (path -> {ref_id, bounds}) that the executor resolves against when
it needs a live ref or click coordinates.

Measured on real fixture pairs (tests/test_axdiff.py enforces this):
  whatsapp step1->2 : 6,583 tok (old) -> ~633 tok    (~10x)
  whatsapp step3->4 : 12,004 tok (old) -> ~2,214 tok (~5x)
"""
from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from typing import Any

# Attributes that change between snapshots without the UI meaningfully changing.
# They never enter the diffed content; ref_id/bounds live in the sidecar instead.
EPHEMERAL_KEYS = frozenset({
    "ref_id",
    "snapshot_id",
    "bounds",
    "available_actions",
    "children_count",
    "pid",
    "process_id",
    "window_id",
})

# States derivable from bounds/scroll position; they flap between captures and
# say nothing about whether an action landed.
STATE_NOISE = frozenset({"offscreen"})


def extract_tree(payload: Any) -> dict:
    """Accept a raw tree, an agent-desktop envelope, or a JSON string."""
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise TypeError(f"expected dict tree, got {type(payload).__name__}")
    if "data" in payload and isinstance(payload["data"], dict):
        inner = payload["data"]
        if "tree" in inner:
            return inner["tree"]
    if "tree" in payload and isinstance(payload["tree"], dict):
        return payload["tree"]
    return payload


def identity_key(node: dict) -> str:
    role = node.get("role", "")
    name = node.get("name", node.get("label", ""))
    return f"{role}:{name}"


def flatten(tree: Any) -> tuple[dict[str, dict], dict[str, dict]]:
    """Flatten a tree into (content, sidecar), both keyed by structural path.

    content[path] -> stable attributes (what gets diffed)
    sidecar[path] -> {"ref_id": ..., "bounds": ...} (what the executor resolves)
    """
    tree = extract_tree(tree)
    content: dict[str, dict] = {}
    sidecar: dict[str, dict] = {}

    def visit(node: dict, path: str) -> None:
        attrs = {}
        for k, v in node.items():
            if k == "children" or k in EPHEMERAL_KEYS:
                continue
            if k == "states" and isinstance(v, list):
                v = sorted(s for s in v if s not in STATE_NOISE)
                if not v:
                    continue
            attrs[k] = v
        content[path] = attrs

        ref = node.get("ref_id")
        bounds = node.get("bounds")
        if ref is not None or bounds is not None:
            sidecar[path] = {"ref_id": ref, "bounds": bounds}

        counts: dict[str, int] = {}
        for child in node.get("children", []):
            if not isinstance(child, dict):
                continue
            key = identity_key(child)
            counts[key] = counts.get(key, 0) + 1
            visit(child, f"{path}/{key}[{counts[key]}]")

    visit(tree, "")
    return content, sidecar


def to_lines(content: dict[str, dict]) -> list[str]:
    return [
        f"{path} => {json.dumps(attrs, sort_keys=True, ensure_ascii=False)}\n"
        for path, attrs in sorted(content.items())
    ]


@dataclass
class DiffResult:
    text: str
    added: int
    removed: int
    sidecar: dict[str, dict] = field(repr=False, default_factory=dict)

    @property
    def changed(self) -> int:
        return self.added + self.removed

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.text)

    @property
    def is_empty(self) -> bool:
        return self.changed == 0


def diff(
    prev: Any,
    curr: Any,
    context_lines: int = 0,
    from_label: str = "S_prev",
    to_label: str = "S_curr",
) -> DiffResult:
    """Unified diff of two tree states, ephemeral churn excluded.

    context_lines defaults to 0: on a path-keyed flat representation the path
    is the context, so surrounding lines are pure token waste.
    """
    prev_content, _ = flatten(prev)
    curr_content, curr_sidecar = flatten(curr)

    lines = list(difflib.unified_diff(
        to_lines(prev_content),
        to_lines(curr_content),
        fromfile=from_label,
        tofile=to_label,
        n=context_lines,
    ))

    added = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
    text = "".join(lines) if lines else "(no state change detected)\n"
    return DiffResult(text=text, added=added, removed=removed, sidecar=curr_sidecar)


def resolve(path: str, sidecar: dict[str, dict]) -> dict | None:
    """Resolve a structural path to its live ref/bounds from the latest capture."""
    return sidecar.get(path)


def estimate_tokens(text: str) -> int:
    return len(text) // 4
