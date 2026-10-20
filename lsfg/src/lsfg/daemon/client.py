"""Client side of the daemon protocol (newline-delimited JSON over ~/.lsfg/run/lsfg.sock).

try_run() returns None when no daemon is listening, so the CLI runs the task in-process.
"""
from __future__ import annotations

import json
import socket
import sys

from .. import config

EXIT = {"SUCCESS": 0, "DRY_RUN": 0, "FAILED": 1, "NEEDS_USER": 2, "BLOCKED_BY_SAFETY": 3, "BUDGET": 4,
        "CANCELLED": 1}


def connect(timeout: float = 0.2) -> socket.socket | None:
    path = config.SOCKET_PATH
    if not path.exists():
        return None
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(path))
    except OSError:
        s.close()
        return None
    s.settimeout(None)
    return s


def request(msg: dict, on_event=None) -> dict | None:
    s = connect()
    if s is None:
        return None
    f = s.makefile("rwb")
    try:
        f.write((json.dumps(msg) + "\n").encode())
        f.flush()
        for line in f:
            ev = json.loads(line.decode())
            if ev.get("type") == "ask":
                try:
                    answer = input(ev.get("text", "") + " ").strip()
                except EOFError:
                    answer = ""
                f.write((json.dumps({"type": "answer", "text": answer}) + "\n").encode())
                f.flush()
                continue
            if ev.get("type") == "result":
                return ev
            if on_event:
                on_event(ev)
    finally:
        try:
            f.close()
            s.close()
        except OSError:
            pass
    return None


def try_run(task: str, *, dry_run: bool, yes: bool, learn: bool, as_json: bool) -> int | None:
    def show(ev):
        if ev.get("type") == "line":
            print(ev.get("text", ""), flush=True)

    res = request({"type": "run", "task": task, "dry_run": dry_run, "yes": yes, "learn": learn,
                   "interactive": sys.stdin.isatty()}, on_event=show)
    if res is None:
        return None
    if as_json:
        print(json.dumps(res.get("result"), indent=2, default=str))
    else:
        r = res.get("result") or {}
        print(res.get("summary", r.get("status", "")))
    return EXIT.get((res.get("result") or {}).get("status", "FAILED"), 1)
