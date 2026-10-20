"""Cancellation: Ctrl-C (SIGINT) and the physical Esc key (implementation.md §15.3).

Session.check() polls both between AX batches, polls, and steps. lsfg's own Esc posts come from
a private event source and pause the check for 200 ms, so an `explore` Esc never cancels itself.
"""
from __future__ import annotations

import signal


def install(session) -> None:
    def handler(signum, frame):
        session.cancel.set()
        raise KeyboardInterrupt
    try:
        signal.signal(signal.SIGINT, handler)
    except ValueError:
        pass                                    # not the main thread (daemon worker)
