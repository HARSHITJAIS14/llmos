"""Safety rules (implementation.md §16).

A step is irreversible if the planner says so OR the target's label looks like Send/Delete/Pay
(defense in depth). Irreversible steps need passing pre-checks, are never retried automatically
(a "failed" Send might have sent), and ask for confirmation unless configured otherwise.
"""
from __future__ import annotations

import re
import sys

from ..errors import SafetyBlocked, UserAborted
from ..types import Step

DENYLIST = frozenset({
    "com.apple.MobileSMS", "com.apple.Passwords", "com.apple.keychainaccess",
    "com.1password.1password", "com.agilebits.onepassword7", "com.bitwarden.desktop",
})

IRREVERSIBLE_LABEL = re.compile(
    r"^(send|delete|remove|erase|trash|empty trash|pay|buy|purchase|order|checkout|submit|post|"
    r"publish|share|transfer|confirm|sign out|log out|format|uninstall|discard|don['’]t save|"
    r"reply all|forward|call|voice call|video call|audio call|start call|dial)\b", re.I)   # a call rings someone

MESSAGING_APPS = frozenset({"net.whatsapp.WhatsApp", "com.apple.MobileSMS", "ru.keepcoder.Telegram",
                            "com.tinyspeck.slackmacgap", "com.hnc.Discord", "com.apple.mail",
                            "com.microsoft.Outlook", "com.microsoft.teams2", "org.whispersystems.signal-desktop"})


def denied(bundle_id: str, extra: list[str] | None = None) -> bool:
    return bundle_id in DENYLIST or bundle_id in set(extra or [])


def label_looks_irreversible(text: str) -> bool:
    return bool(IRREVERSIBLE_LABEL.search((text or "").strip()))


def return_in_compose(step: Step, bundle_id: str) -> bool:
    """A Return hotkey while a messaging app is the target sends the message."""
    return step.op == "hotkey" and bundle_id in MESSAGING_APPS and \
        str(step.params.get("keys", "")).strip().lower() in ("return", "enter", "cmd+return", "cmd+enter")


def submit_sends(bundle_id: str) -> bool:
    """Pressing Return after typing in a messaging or mail app sends the message."""
    return bundle_id in MESSAGING_APPS


def confirm(summary: str, *, yes: bool, interactive: bool, prompt=None) -> None:
    if yes:
        return
    if not interactive:
        raise SafetyBlocked(f"needs confirmation: {summary} (run with --yes to allow)")
    try:
        answer = (prompt or input)(f"\n  About to: {summary}\n  Continue? [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in ("y", "yes"):
        raise UserAborted(f"you declined: {summary}")
