"""Readiness verdicts for a walked snapshot (implementation.md §6.8; LAW-LIFE-12 adapted).

The ladder's actions (activate once when busy, continue at the frontier, poll a tiny tree
after launch) live in Session.observe; this module only judges what a snapshot is worth.
"""
from __future__ import annotations

from ..types import Snapshot

ORDER = ("OPAQUE", "UNTRUSTED", "READ_ONLY_HIDDEN", "TRUST_PREFIX", "TRUST")


def assess(snap: Snapshot) -> str:
    root = snap.root()
    n = len(snap.nodes)
    if root is None:
        return "UNTRUSTED"
    if n <= 1 and root.children_total > 0:
        return "OPAQUE"                     # LAW-LIFE-8: advertises children, delivers none (Telegram)
    if n <= 12:
        return "UNTRUSTED"                  # LAW-LIFE-11: launch transient / husk
    if not snap.on_screen:
        return "READ_ONLY_HIDDEN"           # LAW-LIFE-5: reading is fine, activate before acting
    if snap.truncated & {"nodes", "deadline", "fanout", "app_busy"}:
        return "TRUST_PREFIX"               # LAW-LIFE-7: trust the prefix, never drill
    return "TRUST"


def at_least(readiness: str, floor: str) -> bool:
    return ORDER.index(readiness) >= ORDER.index(floor)
