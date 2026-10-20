"""Every shared dataclass (implementation.md §5).

Refs (live AXUIElementRefs) live in memory only. Nothing here that holds a ref
is ever serialized; routes store Selectors, never refs or aliases (LAW-ID-8).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

Rect = tuple[float, float, float, float]  # x, y, w, h in global points


@dataclass(slots=True)
class Node:
    alias: str                                  # "e17": stable for the session (ax/identity.py)
    key: tuple[int, int]                        # (pid, CFHash(ref))
    ref: Any                                    # AXUIElementRef, or None for fixture nodes
    role: str                                   # normalized role (ax/normalize.py)
    subrole: str | None = None
    name: str = ""
    value: str | int | float | bool | None = None
    value_len: int = 0
    description: str = ""
    help: str = ""
    placeholder: str = ""
    identifier: str = ""
    dom_id: str = ""
    url: str = ""
    states: set[str] = field(default_factory=set)
    bounds: Rect | None = None
    depth: int = 0
    parent: str | None = None
    children: list[str] = field(default_factory=list)
    children_total: int = 0
    actions: frozenset[str] | None = None       # raw AX action names; None = not fetched yet
    caps: dict[str, bool] = field(default_factory=dict)
    caps_preset: bool = False                   # fixtures: caps came from agent-desktop
    region: str = "unknown"
    title_ref: Any = None                       # AXTitleUIElement, read lazily for the name

    @property
    def center(self) -> tuple[float, float] | None:
        if self.bounds is None:
            return None
        x, y, w, h = self.bounds
        return (x + w / 2.0, y + h / 2.0)

    @property
    def zero_area(self) -> bool:
        return self.bounds is not None and (self.bounds[2] <= 0 or self.bounds[3] <= 0)

    @property
    def area(self) -> float:
        if self.bounds is None:
            return 0.0
        return max(0.0, self.bounds[2]) * max(0.0, self.bounds[3])


@dataclass(slots=True)
class Snapshot:
    pid: int
    bundle_id: str
    app_name: str
    framework: str
    stack: str
    root_alias: str | None = None
    root_kind: str = "window"                   # window | sheet | dialog | popover | app
    window_title: str = ""
    window_bounds: Rect | None = None
    nodes: dict[str, Node] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    frontier: list[str] = field(default_factory=list)
    truncated: set[str] = field(default_factory=set)
    readiness: str = "TRUST"                    # TRUST | TRUST_PREFIX | READ_ONLY_HIDDEN | UNTRUSTED | OPAQUE
    signature: str = ""
    timings_ms: dict[str, int] = field(default_factory=dict)
    ax_calls: int = 0
    captured_at: float = 0.0
    cg_window_id: int | None = None
    on_screen: bool = True

    def node(self, alias: str | None) -> Node | None:
        return self.nodes.get(alias) if alias else None

    def iter(self) -> Iterator[Node]:
        for alias in self.order:
            node = self.nodes.get(alias)
            if node is not None:
                yield node

    def root(self) -> Node | None:
        return self.node(self.root_alias)

    def subtree(self, alias: str) -> list[Node]:
        """Pre-order list of `alias` and everything walked below it."""
        out: list[Node] = []
        stack = [alias]
        while stack:
            node = self.nodes.get(stack.pop())
            if node is None:
                continue
            out.append(node)
            stack.extend(reversed(node.children))
        return out

    def ancestors(self, alias: str) -> list[Node]:
        out: list[Node] = []
        node = self.nodes.get(alias)
        while node is not None and node.parent:
            node = self.nodes.get(node.parent)
            if node is not None:
                out.append(node)
        return out

    def webareas(self) -> list[Node]:
        return [n for n in self.iter() if n.role == "webarea"]

    def in_web(self, alias: str) -> bool:
        return any(a.role == "webarea" for a in self.ancestors(alias))


@dataclass(frozen=True, slots=True)
class Clause:
    """One level of a selector (resolve/selector.py)."""
    role: str | None = None
    ident: str | None = None                    # AXIdentifier
    ident_prefix: bool = False
    dom_id: str | None = None                   # AXDOMIdentifier
    name: str | None = None
    name_mode: str = "exact"                    # "exact" | "contains"
    value: str | None = None                    # identity lives in value (LAW-ID-4)
    nth: int | None = None                      # 0-based pre-order index among equal matches


@dataclass(frozen=True, slots=True)
class Selector:
    scope: tuple[Clause, ...] = ()
    target: Clause = Clause()
    special: str | None = None                  # "focused" | "chosen" | "alias:e12"


@dataclass(slots=True)
class Check:
    kind: str                                   # verify/checks.py KINDS
    app: str
    params: dict
    group: int = 0                              # same group = OR, different groups = AND
    when: str = "post"                          # "pre" | "post"

    def to_json(self) -> dict:
        return {"k": self.kind, "app": self.app, **self.params, "g": self.group, "when": self.when}


@dataclass(slots=True)
class Step:
    index: int
    op: str                                     # plan/schema.py OPS
    app: str
    params: dict
    risk: str = "safe"                          # "safe" | "irreversible"
    pre: list[Check] = field(default_factory=list)
    post: list[Check] = field(default_factory=list)

    def to_json(self) -> dict:
        return {"op": self.op, "app": self.app, **self.params, "risk": self.risk,
                "pre": [c.to_json() for c in self.pre], "post": [c.to_json() for c in self.post]}


@dataclass(slots=True)
class Plan:
    steps: list[Step]
    source: str = "planner"                     # "intent:<name>" | "route:<id>" | "planner" | "replan" | "file"

    def to_json(self) -> dict:
        return {"source": self.source, "steps": [s.to_json() for s in self.steps]}


@dataclass(slots=True)
class StepResult:
    index: int
    op: str
    status: str                                 # PASS | FAIL | SKIPPED | ASKED
    error: str | None = None                    # errors.py class name
    detail: str = ""
    resolved: dict | None = None
    mode: str | None = None                     # SEMANTIC | KEYBOARD | POINTER | OCR | LAUNCH_SERVICES | MENU
    timings_ms: dict[str, int] = field(default_factory=dict)
    check_results: list[dict] = field(default_factory=list)
    recovery: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TaskResult:
    status: str                                 # SUCCESS | FAILED | NEEDS_USER | BLOCKED_BY_SAFETY | BUDGET | CANCELLED
    task: str
    steps: list[StepResult] = field(default_factory=list)
    total_ms: int = 0
    opus_calls: int = 0
    jev_calls: int = 0
    tokens: dict = field(default_factory=dict)
    cost_usd: float = 0.0
    source: str = ""
    route_id: int | None = None
    trace_path: str = ""
    reason: str = ""


@dataclass(slots=True)
class AppEntry:
    """An installed (or running) app from the app index (act/apps.py)."""
    name: str
    bundle_id: str
    path: str
    version: str = ""
    build: str = ""
    display_name: str = ""


@dataclass(slots=True)
class WindowInfo:
    ref: Any
    title: str = ""
    bounds: Rect | None = None
    role: str = ""
    subrole: str | None = None
    minimized: bool = False
    focused: bool = False
    main: bool = False
    fullscreen: bool = False
    modal: bool = False
    sheets: list = field(default_factory=list)
    cg_id: int | None = None
    on_screen: bool = False

    @property
    def area(self) -> float:
        if self.bounds is None:
            return 0.0
        return max(0.0, self.bounds[2]) * max(0.0, self.bounds[3])
