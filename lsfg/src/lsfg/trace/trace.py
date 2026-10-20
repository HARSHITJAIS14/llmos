"""JSONL traces in ~/.lsfg/traces/YYYY-MM-DD/<task_id>.jsonl (implementation.md §18.1).

Local only. With trace.store_ui_text = false, the task text is hashed and UI strings are
dropped by the callers (they pass `store_ui_text` through).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from .. import config


class Tracer:
    def __init__(self, task: str, store_ui_text: bool = True, root: Path | None = None) -> None:
        self.task_id = time.strftime("%H%M%S-") + uuid.uuid4().hex[:6]
        day = time.strftime("%Y-%m-%d")
        base = (root or config.TRACE_DIR) / day
        base.mkdir(parents=True, exist_ok=True)
        self.path = str(base / f"{self.task_id}.jsonl")
        self.store_ui_text = store_ui_text
        self._f = open(self.path, "a", encoding="utf-8")
        self._t0 = time.monotonic()
        shown = task if store_ui_text else "sha1:" + hashlib.sha1(task.encode()).hexdigest()[:12]
        self.event("task_start", task=shown, pid=os.getpid())

    def event(self, kind: str, **fields: Any) -> None:
        rec = {"t": round((time.monotonic() - self._t0) * 1000), "type": kind, **fields}
        try:
            self._f.write(json.dumps(rec, default=str, ensure_ascii=False) + "\n")
            self._f.flush()
        except (OSError, ValueError):
            pass

    def close(self) -> None:
        try:
            self._f.close()
        except OSError:
            pass


def prune(keep_runs: int, root: Path | None = None) -> None:
    base = root or config.TRACE_DIR
    if not base.exists():
        return
    files = sorted(base.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[keep_runs:]:
        try:
            old.unlink()
        except OSError:
            pass
