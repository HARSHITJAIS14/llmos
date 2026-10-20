"""The warm daemon (implementation.md §17.2; reasoning.md D26).

Keeps PyObjC, the app index, SQLite, the alias tables and the HTTP/2 connections to TypeSafe and
Anthropic warm (JEV measured 613 ms cold vs ~350 ms warm). Unix socket, mode 0600, one task at
a time. Start it from your terminal: macOS gives a child the terminal's Accessibility grant.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import asdict

from .. import config
from . import client


def _send(f, obj: dict) -> None:
    f.write((json.dumps(obj, default=str) + "\n").encode())
    f.flush()


def serve() -> int:
    config.ensure_dirs()
    path = config.SOCKET_PATH
    if client.connect() is not None:
        print("lsfg daemon is already running", file=sys.stderr)
        return 1
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    from ..engine import Engine
    from ..memory.store import Memory
    engine = Engine(memory=Memory(), interactive=True)
    _warm(engine)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(path))
    os.chmod(path, 0o600)
    srv.listen(4)
    srv.settimeout(0.5)
    print(f"lsfg daemon listening on {path} (pid {os.getpid()})", flush=True)
    from ..act.apps import sync
    try:
        while True:
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                sync()                    # no event loop here: keep app state fresh while idle
                continue
            conn.settimeout(None)
            f = conn.makefile("rwb")
            try:
                line = f.readline()
                if not line:
                    continue
                req = json.loads(line.decode())
                kind = req.get("type")
                if kind == "ping":
                    _send(f, {"type": "result", "result": {"status": "SUCCESS"}, "summary": "pong"})
                elif kind == "stop":
                    _send(f, {"type": "result", "result": {"status": "SUCCESS"}, "summary": "stopping"})
                    return 0
                elif kind == "run":
                    _run(engine, req, f)
            except (OSError, ValueError) as e:
                print(f"client error: {e}", file=sys.stderr)
            finally:
                try:
                    f.close()
                    conn.close()
                except OSError:
                    pass
    finally:
        srv.close()
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _run(engine, req: dict, f) -> None:
    def out(text: str) -> None:
        _send(f, {"type": "line", "text": text})

    def prompt(text: str) -> str:
        _send(f, {"type": "ask", "text": text})
        reply = f.readline()
        return (json.loads(reply.decode()).get("text") or "") if reply else ""

    engine.out, engine.prompt = out, prompt
    engine.interactive = bool(req.get("interactive"))
    result = engine.run(req.get("task", ""), dry_run=bool(req.get("dry_run")), yes=bool(req.get("yes")),
                        learn=bool(req.get("learn", True)))
    summary = (f"{'done' if result.status == 'SUCCESS' else result.status.lower()} in {result.total_ms / 1000:.1f} s"
               f" · {result.opus_calls} Opus · {result.jev_calls} JEV · {result.source}"
               + (f"\n  {result.reason}" if result.reason and result.status != "SUCCESS" else ""))
    _send(f, {"type": "result", "result": asdict(result), "summary": summary})


def _warm(engine) -> None:
    t0 = time.perf_counter()
    try:
        if engine.jev is not None:
            engine.jev.ping()                                  # TLS + HTTP/2 set up once
    except Exception as e:
        print(f"JEV warm-up failed: {e}", file=sys.stderr)
    print(f"warm in {(time.perf_counter() - t0) * 1000:.0f} ms", flush=True)


def cli(action: str) -> int:
    if action == "start":
        if client.connect() is not None:
            print("already running")
            return 0
        config.ensure_dirs()
        log = open(config.RUN_DIR / "daemon.log", "a")
        subprocess.Popen([sys.executable, "-m", "lsfg.daemon.server"], stdout=log, stderr=log,
                         stdin=subprocess.DEVNULL, start_new_session=True)
        for _ in range(100):
            time.sleep(0.1)
            if client.connect() is not None:
                print(f"started (log: {config.RUN_DIR / 'daemon.log'})")
                return 0
        print("the daemon did not come up; see the log", file=sys.stderr)
        return 1
    if action == "stop":
        res = client.request({"type": "stop"})
        print("stopped" if res else "not running")
        return 0
    res = client.request({"type": "ping"})
    print("running" if res else "not running")
    return 0 if res else 1


if __name__ == "__main__":
    sys.exit(serve())
