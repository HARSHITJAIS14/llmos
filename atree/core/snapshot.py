"""Skeleton-first capture over the agent-desktop CLI.

The old harness captured `--max-depth 40` + recursive DFS on every step —
that is how a single Notion tree hit 1.9 MB (~473k tokens). agent-desktop
ships `--skeleton` progressive traversal (documented 78-96% reduction on
dense apps); the correct default is skeleton -> identify region -> drill
down only there.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

_FALLBACK_BIN = "/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js"


def agent_bin() -> str:
    return (
        os.environ.get("ATREE_AGENT_DESKTOP")
        or shutil.which("agent-desktop")
        or _FALLBACK_BIN
    )


def run(args: list[str], timeout: float = 30.0) -> dict:
    """Run one agent-desktop command, return its parsed JSON envelope."""
    try:
        res = subprocess.run(
            [agent_bin()] + args, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"agent-desktop timed out after {timeout}s", "args": args}
    try:
        return json.loads(res.stdout)
    except (json.JSONDecodeError, ValueError):
        return {"ok": False, "error": "non-JSON output", "raw": res.stdout[:2000],
                "stderr": res.stderr[:2000], "args": args}


def skeleton(app: str | None = None, window_id: str | None = None) -> dict:
    """Shallow structural overview. Cheap; run this first, always."""
    cmd = ["snapshot", "--skeleton", "-i", "--compact"]
    if window_id:
        cmd += ["--window-id", window_id]
    elif app:
        cmd += ["--app", app]
    return run(cmd)


def drill(ref_id: str, snapshot_id: str, include_bounds: bool = True) -> dict:
    """Expand one truncated region from an existing skeleton snapshot."""
    cmd = ["snapshot", "--root", ref_id, "--snapshot", snapshot_id, "-i"]
    if include_bounds:
        cmd.append("--include-bounds")
    return run(cmd)


def find(app: str | None = None, role: str | None = None, name: str | None = None,
         text: str | None = None, limit: int = 20) -> dict:
    """Targeted element search — cheaper than any snapshot when you know
    what you are looking for. Prefer this for verification reads."""
    cmd = ["find", "--limit", str(limit)]
    if app:
        cmd += ["--app", app]
    if role:
        cmd += ["--role", role]
    if name:
        cmd += ["--name", name]
    if text:
        cmd += ["--text", text]
    return run(cmd)


def pick_window(candidates: list[dict], app: str | None = None) -> str | None:
    """The ghost-window rule (electron.md / catalyst.md), in code: prefer the
    focused window, then a visible one, then one whose title is a real page
    title rather than the bare app name."""
    def score(w: dict) -> tuple:
        title = str(w.get("title", ""))
        real_title = bool(title) and title.lower() != (app or "").lower()
        return (bool(w.get("is_focused")), bool(w.get("visible")), real_title)
    ranked = sorted(candidates, key=score, reverse=True)
    return ranked[0].get("id") if ranked else None


def list_windows(app: str | None = None) -> list[dict]:
    cmd = ["list-windows"]
    if app:
        cmd += ["--app", app]
    env = run(cmd)
    data = env.get("data") if env.get("ok") else None
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("windows", [])
    return []


def capture(app: str | None = None, window_id: str | None = None,
            surface: str | None = None) -> dict:
    """Full-window capture for postcondition evaluation.

    Returns the tree dict (unwrapped). Kept deliberately un-deep: verification
    should target a scope, not re-explore the app. AMBIGUOUS_TARGET (ghost
    windows) is resolved automatically instead of surfacing as a failure.
    """
    cmd = ["snapshot", "-i", "--include-bounds"]
    if surface:
        cmd += ["--surface", surface]
        if app:
            cmd += ["--app", app]
    elif window_id:
        cmd += ["--window-id", window_id]
    elif app:
        cmd += ["--app", app]
    env = run(cmd)

    err = env.get("error") if not env.get("ok") else None
    if isinstance(err, dict) and app and not surface:
        if err.get("code") == "AMBIGUOUS_TARGET" and not window_id:
            wid = pick_window(err.get("details", {}).get("candidates", []), app)
            if wid:
                return capture(app=app, window_id=wid)
        # A window can report visible+focused in list-windows yet expose no AX
        # element (fresh Space switch, Safari). The focused surface still works.
        if err.get("details", {}).get("kind") == "window_without_accessibility_element":
            return capture(app=app, surface="focused")

    if not env.get("ok"):
        raise RuntimeError(f"snapshot failed: {env.get('error', env)}")
    return env


def expand_truncated(tree: dict, snapshot_id: str, max_requests: int = 10) -> dict:
    """Selective drill-down: expand nodes reporting children they did not
    serialize. Bounded — this is the escape hatch, not the default path."""
    budget = [max_requests]

    def visit(node: Any) -> None:
        if not isinstance(node, dict) or budget[0] <= 0:
            return
        ref = node.get("ref_id")
        if node.get("children_count", 0) > 0 and not node.get("children") and ref:
            budget[0] -= 1
            got = drill(ref, snapshot_id)
            if got.get("ok"):
                drilled = got.get("data", {}).get("tree", {})
                if drilled.get("children"):
                    node["children"] = drilled["children"]
        for child in node.get("children", []):
            visit(child)

    visit(tree)
    return tree
