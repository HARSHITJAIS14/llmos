"""The lsfg command line (implementation.md §17.1).

    lsfg "<task>"            run a task (same as: lsfg run "<task>")
    lsfg --prompt            ask for the task in a small dialog, then run it
    lsfg run "<task>" [--dry-run] [--yes] [--no-learn] [--json] [--plan FILE]
    lsfg doctor              permissions, keys, JEV/Anthropic reachability, app index
    lsfg observe APP [--tree|--windows|--menu|--ocr] [--deep]
    lsfg routes [list | show ID | rm ID | disable ID | enable ID]
    lsfg bench [SUITE] [--runs N]
    lsfg daemon [start | stop | status]
    lsfg forget [--traces] [--routes] [--profiles] [--all]
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from . import config

COMMANDS = {"run", "doctor", "observe", "routes", "bench", "daemon", "forget"}
EXIT = {"SUCCESS": 0, "DRY_RUN": 0, "FAILED": 1, "NEEDS_USER": 2, "BLOCKED_BY_SAFETY": 3, "BUDGET": 4,
        "CANCELLED": 1}


def _memory():
    try:
        from .memory.store import Memory
        return Memory()
    except Exception:
        return None


def _engine(interactive: bool | None = None):
    from .engine import Engine
    return Engine(memory=_memory(), interactive=interactive)


def cmd_run(args) -> int:
    task = " ".join(args.task).strip()
    if args.plan:
        from .plan.schema import parse_plan
        with open(args.plan) as f:
            plan = parse_plan(json.load(f), source="file")
    else:
        plan = None
        if not task:
            print("usage: lsfg \"<task>\"", file=sys.stderr)
            return 5
        if not args.local:
            from .daemon.client import try_run
            code = try_run(task, dry_run=args.dry_run, yes=args.yes, learn=not args.no_learn, as_json=args.json)
            if code is not None:
                return code
    eng = _engine()
    result = eng.run(task or args.plan, dry_run=args.dry_run, yes=args.yes, learn=not args.no_learn, plan=plan)
    _print_result(result, args.json)
    return EXIT.get(result.status, 1)


def _print_result(result, as_json: bool) -> None:
    if as_json:
        from dataclasses import asdict
        print(json.dumps(asdict(result), default=str, indent=2))
        return
    tok = result.tokens or {}
    model = []
    if result.opus_calls:
        model.append(f"{result.opus_calls} Opus")
    if result.jev_calls:
        model.append(f"{result.jev_calls} JEV")
    calls = " + ".join(model) if model else "0 model calls"
    cost = f" · ${result.cost_usd:.4f}" if result.cost_usd else ""
    src = f" · {result.source}" if result.source else ""
    head = "done" if result.status == "SUCCESS" else result.status.lower()
    print(f"{head} in {result.total_ms / 1000:.1f} s · {calls}{cost}{src}")
    if result.reason and result.status != "SUCCESS":
        print(f"  {result.reason}")
    if tok.get("opus_in"):
        print(f"  tokens: opus in {tok.get('opus_in')} (cached {tok.get('opus_cached')}) out {tok.get('opus_out')}")
    print(f"  trace: {result.trace_path}")


def cmd_prompt(args) -> int:
    import AppKit
    AppKit.NSApplication.sharedApplication().setActivationPolicy_(1)
    alert = AppKit.NSAlert.alloc().init()
    alert.setMessageText_("lsfg")
    alert.setInformativeText_("What should I do?")
    alert.addButtonWithTitle_("Run")
    alert.addButtonWithTitle_("Cancel")
    field = AppKit.NSTextField.alloc().initWithFrame_(((0, 0), (360, 24)))
    alert.setAccessoryView_(field)
    alert.window().setInitialFirstResponder_(field)
    AppKit.NSApp.activateIgnoringOtherApps_(True)
    if alert.runModal() != AppKit.NSAlertFirstButtonReturn:
        return 0
    task = str(field.stringValue()).strip()
    if not task:
        return 0
    args.task = [task]
    return cmd_run(args)


def cmd_doctor(args) -> int:
    import platform
    import objc
    import Quartz
    from .ax import raw
    cfg = config.load_config()
    ok = True

    def row(name, good, detail="", required=True):
        nonlocal ok
        if required:
            ok = ok and good
        mark = "✓" if good else ("✗" if required else "!")
        print(f"  {mark} {name:<28} {detail}")

    print("lsfg doctor")
    row("macOS", True, platform.mac_ver()[0])
    row("python / pyobjc", sys.version_info >= (3, 12), f"{platform.python_version()} / {objc.__version__}")
    row("Accessibility", raw.trusted(), "" if raw.trusted() else
        "grant it to your terminal/IDE: System Settings > Privacy & Security > Accessibility")
    sc = bool(Quartz.CGPreflightScreenCaptureAccess())
    row("Screen Recording (OCR)", sc, "" if sc else "grant it for OCR: Privacy & Security > Screen Recording")
    row("TYPESAFE_API_KEY (JEV)", bool(cfg.typesafe_api_key), "present" if cfg.typesafe_api_key else
        "missing: JEV choose/explore disabled (put it in ~/.lsfg/.env)", required=False)
    row("ANTHROPIC_API_KEY (planner)", bool(cfg.anthropic_api_key), "present" if cfg.anthropic_api_key else
        "missing: only built-in intents and learned routes will run (put it in ~/.lsfg/.env)", required=False)
    if config.ENV_PATH.exists():
        row("~/.lsfg/.env mode", cfg.env_file_mode_ok, "0600" if cfg.env_file_mode_ok else "run: chmod 600 ~/.lsfg/.env")
    t0 = time.perf_counter()
    from .act.apps import AppIndex
    idx = AppIndex()
    row("app index", len(idx.entries) > 0, f"{len(idx.entries)} apps ({(time.perf_counter() - t0) * 1000:.0f} ms)")
    layout = _keyboard_layout()
    qwerty = layout == "" or any(layout.startswith("com.apple.keylayout." + k) for k in
                                 ("US", "ABC", "British", "Australian", "Canadian", "Irish"))
    row("keyboard layout", qwerty, (layout or "unknown") + ("" if qwerty else
        " (shortcuts assume US key positions; menu commands still work)"), required=False)
    if not args.no_network:
        if cfg.typesafe_api_key:
            from .decide.jev import JevClient
            try:
                ms = JevClient(cfg).ping()
                row("JEV reachable", True, f"{ms:.0f} ms")
            except Exception as e:
                row("JEV reachable", False, str(e)[:80])
        if cfg.anthropic_api_key:
            try:
                import anthropic
                c = anthropic.Anthropic(api_key=cfg.anthropic_api_key, max_retries=0, timeout=10)
                t1 = time.perf_counter()
                c.messages.count_tokens(model=cfg.planner.model, messages=[{"role": "user", "content": "ping"}])
                row("Anthropic reachable", True, f"{(time.perf_counter() - t1) * 1000:.0f} ms ({cfg.planner.model})")
            except Exception as e:
                row("Anthropic reachable", False, str(e)[:80])
    return 0 if ok else 5


def _keyboard_layout() -> str:
    import plistlib
    from pathlib import Path
    p = Path.home() / "Library/Preferences/com.apple.HIToolbox.plist"
    try:
        with open(p, "rb") as f:
            d = plistlib.load(f)
        return str(d.get("AppleCurrentKeyboardLayoutInputSourceID", ""))
    except (OSError, plistlib.InvalidFileException, ValueError):
        return ""


def cmd_observe(args) -> int:
    from .ax import windows
    from .ax import menu as menus
    from .ax.labels import label
    from .plan import digest
    from .safety import policy
    from .session import Session
    from .vision.ocr import OCR
    cfg = config.load_config()
    s = Session(cfg)
    s.ocr = OCR()
    ctx = s.ctx(" ".join(args.app))
    if ctx.pid is None:
        print(f"{ctx.name} is not running")
        return 1
    if args.windows:
        for w in windows.window_candidates(ctx.pid):
            windows.attach_cg(w, ctx.pid)
            print(f"  {w.role:<9} {w.subrole or '-':<18} focused={w.focused!s:<5} main={w.main!s:<5} "
                  f"min={w.minimized!s:<5} on_screen={w.on_screen!s:<5} cg={w.cg_id} bounds={w.bounds} {w.title[:40]!r}")
        for c in windows.cg_windows(ctx.pid):
            print(f"  cg {c['id']:<7} {tuple(round(v) for v in c['bounds'])} ghost={windows.is_ghost_cg(c, windows.window_candidates(ctx.pid))} "
                  f"thumb={windows.is_thumbnail(c)}")
        return 0
    if args.menu:
        t0 = time.perf_counter()
        items = menus.read_menus(ctx.pid)
        print(f"{len(items)} menu items in {(time.perf_counter() - t0) * 1000:.0f} ms")
        for it in items:
            print(f"  {' > '.join(it.path):<60} {it.shortcut:<14} {'' if it.enabled else '(disabled)'}{' ✓' if it.checked else ''}")
        return 0
    snap = s.observe(ctx, deep=args.deep)
    if args.ocr:
        win = windows.pick_window(ctx.pid)
        windows.attach_cg(win, ctx.pid)
        t0 = time.perf_counter()
        boxes = s.ocr.read(win.cg_id, win.bounds) if win and win.cg_id else []
        print(f"{len(boxes)} text boxes in {(time.perf_counter() - t0) * 1000:.0f} ms")
        for b in boxes[:80]:
            print(f"  {b.confidence:.2f} {tuple(round(v) for v in b.bounds)} {b.text[:70]!r}")
        return 0
    if args.tree:
        for n in snap.iter():
            print(f"{'  ' * min(n.depth, 20)}@{n.alias} {n.role} {label(n, snap)[:60]!r} "
                  f"{('#' + n.identifier) if n.identifier else ''} {sorted(n.states) if n.states else ''}")
    else:
        text, _ = digest.build(snap, framework=ctx.framework, denied=policy.denied(ctx.bundle_id))
        print(text)
    print(f"\n[{ctx.framework}/{ctx.stack} · {snap.readiness} · {len(snap.nodes)} nodes · frontier {len(snap.frontier)} · "
          f"truncated {sorted(snap.truncated) or '-'} · {snap.ax_calls} AX calls · {snap.timings_ms}]")
    return 0


def cmd_routes(args) -> int:
    mem = _memory()
    if mem is None:
        print("no route store")
        return 1
    return mem.routes.cli(args.action, args.id)


def cmd_bench(args) -> int:
    from .trace.bench import run_bench
    return run_bench(args.suite, runs=args.runs, yes=args.yes)


def cmd_daemon(args) -> int:
    from .daemon import server
    return server.cli(args.action)


def cmd_forget(args) -> int:
    import shutil
    everything = args.all
    if args.traces or everything:
        shutil.rmtree(config.TRACE_DIR, ignore_errors=True)
        print("traces deleted")
    if args.routes or args.profiles or everything:
        mem = _memory()
        if mem is not None:
            mem.forget(routes=args.routes or everything, profiles=args.profiles or everything)
            print("routes/profiles deleted")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lsfg", description="Fast macOS desktop agent.")
    p.add_argument("--prompt", action="store_true", help="ask for the task in a dialog")
    sub = p.add_subparsers(dest="cmd")
    r = sub.add_parser("run")
    r.add_argument("task", nargs="*")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--yes", action="store_true", help="skip confirmations for irreversible steps")
    r.add_argument("--no-learn", action="store_true")
    r.add_argument("--json", action="store_true")
    r.add_argument("--plan", help="run a hand-written plan JSON file")
    r.add_argument("--local", action="store_true", help="don't use the daemon")
    d = sub.add_parser("doctor")
    d.add_argument("--no-network", action="store_true")
    o = sub.add_parser("observe")
    o.add_argument("app", nargs="+")
    o.add_argument("--tree", action="store_true")
    o.add_argument("--windows", action="store_true")
    o.add_argument("--menu", action="store_true")
    o.add_argument("--ocr", action="store_true")
    o.add_argument("--deep", action="store_true")
    ro = sub.add_parser("routes")
    ro.add_argument("action", nargs="?", default="list")
    ro.add_argument("id", nargs="?")
    b = sub.add_parser("bench")
    b.add_argument("suite", nargs="?")
    b.add_argument("--runs", type=int, default=1)
    b.add_argument("--yes", action="store_true")
    da = sub.add_parser("daemon")
    da.add_argument("action", nargs="?", default="status")
    f = sub.add_parser("forget")
    f.add_argument("--traces", action="store_true")
    f.add_argument("--routes", action="store_true")
    f.add_argument("--profiles", action="store_true")
    f.add_argument("--all", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in COMMANDS and not argv[0].startswith("-"):
        argv = ["run"] + argv
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.prompt:
        ns = parser.parse_args(["run"])
        return cmd_prompt(ns)
    handler = {"run": cmd_run, "doctor": cmd_doctor, "observe": cmd_observe, "routes": cmd_routes,
               "bench": cmd_bench, "daemon": cmd_daemon, "forget": cmd_forget}.get(args.cmd)
    if handler is None:
        parser.print_help()
        return 0
    from .errors import LsfgError
    try:
        return handler(args)
    except LsfgError as e:
        print(f"{e.kind}: {e.message}", file=sys.stderr)
        return 2 if e.kind == "ScreenLocked" else 5
    except KeyboardInterrupt:
        print("cancelled", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
