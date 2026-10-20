"""App cards for the planner (implementation.md §13.2): codex card + live menu shortcuts + learned anchors.

Each card is ≤ ~400 tokens. Cards are sorted by bundle id when sent, so equal app sets are
byte-identical and hit the prompt cache.
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources

from ..ax import menu as menus
from ..errors import LsfgError

MAX_MENU = 20


@lru_cache(maxsize=1)
def _profiles() -> dict:
    try:
        return json.loads(resources.files("lsfg.data.codex").joinpath("profiles.json").read_text())
    except (OSError, ValueError, ModuleNotFoundError):
        return {}


def seed_key(bundle_id: str) -> str | None:
    profs = _profiles()
    if bundle_id in profs:
        return bundle_id
    for key, p in profs.items():
        if p.get("match") == "prefix" and bundle_id.startswith(key):
            return key
    return None


def seed_for(bundle_id: str) -> dict:
    key = seed_key(bundle_id)
    return _profiles().get(key, {}) if key else {}


def codex_card(bundle_id: str) -> str:
    key = seed_key(bundle_id)
    if not key:
        return ""
    try:
        return resources.files("lsfg.data.codex").joinpath("cards", f"{key}.md").read_text().strip()
    except (OSError, FileNotFoundError):
        return ""


def stack_hint(ctx) -> str:
    if ctx.framework in ("electron", "cef"):
        return "Electron/web app: prefer its search box and shortcuts. Clicks go through the pointer."
    if ctx.framework in ("webkit_native", "chromium_browser", "gecko"):
        return "Browser: navigate with open_url; check pages with url. Page content is web."
    if ctx.framework == "wkwebview_webapp":
        return "Safari web app: the whole window is web content."
    if ctx.stack == "opaque":
        return "No usable accessibility tree: plan with keyboard shortcuts and text (OCR) checks."
    if ctx.framework == "qt":
        return "Qt app: elements have no screen bounds; everything goes through accessibility actions."
    return "Native Mac app: elements work in the background."


def card_for(session, ctx) -> str:
    lines = [codex_card(ctx.bundle_id) or f"## {ctx.name} ({ctx.bundle_id}) · {ctx.framework}"]
    lines.append(stack_hint(ctx))
    if ctx.pid is not None:
        try:
            top = menus.top_commands(session.menu_items(ctx), MAX_MENU)
        except LsfgError:
            top = []
        if top:
            lines.append("Menu: " + " · ".join(
                f"{'>'.join(it.path)}{' ' + it.shortcut if it.shortcut else ''}" for it in top))
    learned = (session.profile(ctx.bundle_id) or {}).get("anchors") or []
    if learned:
        lines.append("Learned: " + " · ".join(f"{a['selector']} {a.get('purpose', '')}".strip() for a in learned[:8]))
    return "\n".join(lines)
