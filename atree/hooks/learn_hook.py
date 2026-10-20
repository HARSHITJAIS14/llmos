#!/usr/bin/env python3
"""Stop hook: mine this session's outcomes for fail->pass transitions and
write learning CANDIDATES. Never promotes — that is /ax-learn's batched,
gated job. Zero model turns; always exits 0."""
import json
import re
import sys
import time

from _common import OUTCOMES

if not OUTCOMES.exists():
    sys.exit(0)

from core import ledger  # noqa: E402

records = []
for line in OUTCOMES.read_text().splitlines():
    try:
        records.append(json.loads(line))
    except json.JSONDecodeError:
        continue


def action_kind(cmd: str) -> str:
    m = re.search(r"agent-desktop\S*\s+([a-z-]+)", cmd)
    return m.group(1) if m else "unknown"


# A fail on (app, postcondition) later followed by a pass with a DIFFERENT
# action kind = "strategy A failed, strategy B worked" — exactly one datapoint.
by_target: dict = {}
for r in records:
    key = (r.get("app") or "?", json.dumps(r.get("postcondition", {}), sort_keys=True))
    by_target.setdefault(key, []).append(r)

mined = 0
for (app, _pc), seq in by_target.items():
    fails = [r for r in seq if r["verdict"] == "fail"]
    passes = [r for r in seq if r["verdict"] == "pass"]
    if not fails or not passes:
        continue
    failed_kind = action_kind(fails[0].get("action", ""))
    worked_kind = action_kind(passes[-1].get("action", ""))
    if failed_kind == worked_kind:
        continue
    cid = f"{app.lower().replace(' ', '-')}-{failed_kind}-fails-{worked_kind}-works"
    ledger.record_evidence(
        candidate_id=cid,
        claim=f"In {app}, '{failed_kind}' does not achieve "
              f"{fails[0].get('postcondition', {}).get('description') or 'the target state'} "
              f"but '{worked_kind}' does",
        strategy=f"use {worked_kind} instead of {failed_kind}",
        ev=ledger.Evidence(
            ts=passes[-1].get("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
            route="session", app=app, outcome="fail-then-pass",
            detail=fails[0].get("detail", "")[:200],
        ),
    )
    mined += 1

# Consumed: outcomes roll into the ledger; keep a rotating copy for debugging.
OUTCOMES.rename(OUTCOMES.with_suffix(f".{int(time.time())}.done"))
sys.exit(0)
