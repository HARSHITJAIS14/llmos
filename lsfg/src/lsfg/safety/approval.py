"""Approval before an irreversible action (implementation.md §16.1).

Everything up to the final action runs first (the message is typed and read back), then the
user sees exactly what will happen: app, action, recipient hint, the draft as it landed, and
the checks that passed. Nothing is sent without a yes. In a terminal it asks there; with no
terminal (the Shortcuts hotkey, a non-interactive daemon client) it shows a native dialog;
if neither is possible the step is blocked.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

from ..errors import SafetyBlocked, UserAborted

DIALOG_TIMEOUT_S = 120.0


@dataclass
class Approval:
    app: str
    action: str                                  # e.g. 'press Return (this sends the message)'
    target: str = ""                             # e.g. 'chat "Priya Sharma"'
    draft: str = ""                              # the text as it landed in the field
    checks: list[str] = field(default_factory=list)
    note: str = ""

    def card(self) -> str:
        lines = ["", "  ┌ Approve this action? It can't be undone.", f"  │ app:     {self.app}",
                 f"  │ action:  {self.action}"]
        if self.target:
            lines.append(f"  │ to:      {self.target}")
        if self.draft:
            shown = self.draft if len(self.draft) <= 300 else self.draft[:300] + "…"
            lines.append(f"  │ text:    {shown!r}")
        for c in self.checks[:6]:
            lines.append(f"  │ check:   {c}")
        if self.note:
            lines.append(f"  │ note:    {self.note}")
        lines.append("  └")
        return "\n".join(lines)

    def one_line(self) -> str:
        bits = [f"{self.action} in {self.app}"]
        if self.target:
            bits.append(f"to {self.target}")
        if self.draft:
            bits.append(f"text {self.draft[:80]!r}")
        return " · ".join(bits)


def ask(approval: Approval, *, yes: bool, interactive: bool, prompt=None, dialog: bool = True) -> None:
    """Return if approved. Raise UserAborted on no, SafetyBlocked when nobody can be asked."""
    if yes:
        return
    if interactive:
        try:
            answer = (prompt or input)(approval.card() + "\n  Do it? [y/N] ").strip().lower()
        except EOFError:
            answer = ""
        if answer in ("y", "yes"):
            return
        raise UserAborted(f"you declined: {approval.one_line()}")
    if dialog and _gui_available():
        if _dialog(approval):
            return
        raise UserAborted(f"you declined (or the dialog timed out): {approval.one_line()}")
    raise SafetyBlocked(f"needs your approval: {approval.one_line()} (run in a terminal, or pass --yes)")


def _gui_available() -> bool:
    try:
        import Quartz
        session = Quartz.CGSessionCopyCurrentDictionary()
        return bool(session) and bool(session.get("kCGSSessionOnConsoleKey", True))
    except Exception:
        return False


def _dialog(approval: Approval) -> bool:
    """A floating native alert. Times out as a 'no' after 2 minutes."""
    import AppKit
    import Foundation
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    alert = AppKit.NSAlert.alloc().init()
    alert.setMessageText_(f"lsfg wants to {approval.action} in {approval.app}")
    info = []
    if approval.target:
        info.append(f"To: {approval.target}")
    if approval.draft:
        info.append(f"Text: {approval.draft[:400]}")
    info += approval.checks[:4]
    alert.setInformativeText_("\n".join(info) or "This can't be undone.")
    alert.addButtonWithTitle_("Do it")
    alert.addButtonWithTitle_("Cancel")
    alert.setAlertStyle_(AppKit.NSAlertStyleWarning)
    win = alert.window()
    win.setLevel_(AppKit.NSStatusWindowLevel)            # float above other apps (activation may be refused)
    timer = Foundation.NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
        DIALOG_TIMEOUT_S, app, "abortModal", None, False)
    Foundation.NSRunLoop.currentRunLoop().addTimer_forMode_(timer, AppKit.NSModalPanelRunLoopMode)
    try:
        app.activateIgnoringOtherApps_(True)
    except Exception:
        pass
    result = alert.runModal()
    timer.invalidate()
    return result == AppKit.NSAlertFirstButtonReturn


def terminal_interactive() -> bool:
    return sys.stdin.isatty()
