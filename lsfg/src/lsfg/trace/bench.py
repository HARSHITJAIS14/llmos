"""The bench runner (implementation.md §18.3).

Each task has its own `verify` checks, evaluated after the run. The bench never trusts the
plan's own checks, so a weak check can't hide a failure.
"""
from __future__ import annotations

import statistics
from importlib import resources
from pathlib import Path

import yaml

from ..verify.checks import from_json
from ..verify.evaluate import wait_checks


def load_suite(path: str | None) -> list[dict]:
    if path:
        return yaml.safe_load(Path(path).read_text()) or []
    return yaml.safe_load(resources.files("lsfg.data").joinpath("bench", "suite.yaml").read_text()) or []


def run_bench(path: str | None, runs: int = 1, yes: bool = False) -> int:
    from ..engine import Engine
    from ..memory.store import Memory
    suite = load_suite(path)
    eng = Engine(memory=Memory(), interactive=not yes)
    rows = []
    for t in suite:
        if t.get("needs") == "planner" and eng.planner is None:
            rows.append((t["id"], "skipped (no ANTHROPIC_API_KEY)", [], []))
            continue
        oks, times, calls = [], [], []
        for _ in range(runs):
            res = eng.run(t["task"], yes=yes)
            checks = [from_json(c) for c in t.get("verify") or []]
            ok, _, _ = wait_checks(checks, eng.session, float(t.get("verify_timeout", 3.0))) if checks else (res.status == "SUCCESS", [], 0)
            oks.append(bool(ok and res.status == "SUCCESS"))
            times.append(res.total_ms)
            calls.append(res.opus_calls + res.jev_calls)
            if t.get("teardown"):
                from ..plan.schema import parse_plan
                eng.run(f"teardown {t['id']}", plan=parse_plan({"steps": t["teardown"]}, source="file"), yes=True,
                        learn=False)
        rows.append((t["id"], f"{sum(oks)}/{len(oks)}", times, calls))
    print(f"\n| task | success | p50 ms | p95 ms | model calls |\n|---|---|---|---|---|")
    total_ok = total = 0
    for tid, succ, times, calls in rows:
        if times:
            p50 = int(statistics.median(times))
            p95 = int(sorted(times)[max(0, int(len(times) * 0.95) - 1)])
            print(f"| {tid} | {succ} | {p50} | {p95} | {statistics.mean(calls):.1f} |")
            a, b = succ.split("/")
            total_ok, total = total_ok + int(a), total + int(b)
        else:
            print(f"| {tid} | {succ} | - | - | - |")
    if total:
        print(f"\noverall {total_ok}/{total} = {100 * total_ok / total:.0f}%")
    return 0 if total and total_ok == total else 1
