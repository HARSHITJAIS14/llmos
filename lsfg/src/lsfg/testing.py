"""Fixture loading: agent-desktop census captures → lsfg Snapshots (implementation.md §19.1).

agent-desktop already uses the codex role/action vocabulary, so capabilities come preset and
there are no refs. This gives unit tests 24 real apps' trees, offline.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .ax.caps import preset_from_actions
from .ax.labels import fill_regions
from .ax.normalize import norm
from .types import Node, Snapshot

CENSUS = Path(os.environ.get("LSFG_CENSUS", Path(__file__).resolve().parents[3] / "Ax_analysis"))
APPS = ("antigravity_ide brave_browser calendar claude discord finder firefox gemini google_chrome keynote "
        "microsoft_word music notes notion obs reminders safari telegram textedit utm vlc whatsapp yt_music "
        "zoom_us").split()


def raw_capture(app: str, kind: str = "full") -> dict | None:
    p = CENSUS / app / f"{kind}.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
    except (OSError, ValueError):
        return None
    return d.get("data") if d.get("ok") else None


def load_snapshot(app: str, kind: str = "full", framework: str = "", stack: str = "native") -> Snapshot | None:
    data = raw_capture(app, kind)
    if data is None:
        return None
    if kind == "forced" and app == "music":
        return None                                             # mislabeled: it is YT Music (LAW-STR-12)
    snap = Snapshot(pid=0, bundle_id="", app_name=data.get("app", app), framework=framework, stack=stack)
    counter = [0]

    def add(d: dict, depth: int, parent: str | None) -> str:
        counter[0] += 1
        alias = f"e{counter[0]}"
        nid = d.get("native_id") or {}
        b = d.get("bounds") or None
        bounds = (float(b.get("x", 0)), float(b.get("y", 0)), float(b.get("width", 0)), float(b.get("height", 0))) if b else None
        v = d.get("value")
        node = Node(alias=alias, key=(0, counter[0]), ref=None, role=d.get("role", "unknown"),
                    name=norm(d.get("name", "")), value=v, value_len=len(v) if isinstance(v, str) else 0,
                    description=norm(d.get("description", "")),
                    identifier=nid.get("value", "") if nid.get("kind") == "ax_identifier" else "",
                    dom_id=nid.get("value", "") if nid.get("kind") == "ax_dom_identifier" else "",
                    states=set(d.get("states") or []), bounds=bounds, depth=depth, parent=parent)
        preset_from_actions(node, d.get("available_actions") or [])
        kids = d.get("children") or []
        node.children_total = int(d.get("children_count") or len(kids))
        snap.nodes[alias] = node
        snap.order.append(alias)
        if node.children_total > len(kids):
            snap.frontier.append(alias)
        for c in kids:
            node.children.append(add(c, depth + 1, alias))
        return alias

    snap.root_alias = add(data["tree"], 0, None)
    root = snap.root()
    snap.window_bounds = root.bounds if root else None
    if data.get("complete") is False and int(data.get("nodes_observed") or 0) > len(snap.nodes):
        snap.truncated.add("nodes")
    fill_regions(snap)
    return snap


def windows_listing(app: str) -> list[dict]:
    p = CENSUS / app / "windows.json"
    if not p.exists():
        return []
    try:
        d = json.loads(p.read_text())
    except (OSError, ValueError):
        return []
    if isinstance(d, dict):
        d = d.get("data", d)
        d = d.get("windows", d) if isinstance(d, dict) else d
    return d if isinstance(d, list) else []
