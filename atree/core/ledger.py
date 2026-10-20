"""Evidence ledger + promotion gate for learnings (pitch §4).

Learning is an aggregation over the verification log, not an act of
authorship. The model is never asked "what did you learn?" — it is asked
"which claims does the ledger now support?", and this module is the gate
that refuses to promote a claim the evidence does not carry.

Tiers:
  observed      n=1, hook-written              learnings/candidates/
  corroborated  n>=2 independent runs          learnings/candidates/
  confirmed     corroborated AND has a repro   skills/atree/references/ (human step)
  refuted       2 verification failures        learnings/archive/

The gate runs BEFORE any model judgment: /ax-learn calls `can_promote` and a
candidate that fails it is simply not shown as promotable.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

MIN_EVIDENCE = 2
REFUTE_AFTER = 2

_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[1]))
LEARNINGS_DIR = _ROOT / "learnings"
CANDIDATES_DIR = LEARNINGS_DIR / "candidates"
ARCHIVE_DIR = LEARNINGS_DIR / "archive"
LEDGER_PATH = LEARNINGS_DIR / "ledger.jsonl"


@dataclass
class Evidence:
    ts: str                    # ISO timestamp of the run
    route: str                 # task/route the observation came from
    app: str
    outcome: str               # "fail-then-pass" | "pass" | "fail"
    detail: str = ""


@dataclass
class Candidate:
    id: str                    # kebab-case, e.g. electron-axpress-swallowed
    claim: str
    strategy: str
    archetype: str = ""
    apps: list[str] = field(default_factory=list)
    status: str = "observed"   # observed | corroborated | refuted
    evidence: list[dict] = field(default_factory=list)
    repro: str = ""            # fixture path or route id that regresses without it
    observed_with: dict = field(default_factory=dict)
    failures: int = 0          # post-confirmation verification failures

    def path(self) -> Path:
        return CANDIDATES_DIR / f"{self.id}.json"


def _load(candidate_id: str) -> Candidate | None:
    for d in (CANDIDATES_DIR, ARCHIVE_DIR):  # refuted candidates stay queryable
        p = d / f"{candidate_id}.json"
        if p.exists():
            return Candidate(**json.loads(p.read_text()))
    return None


def _save(c: Candidate) -> None:
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    c.path().write_text(json.dumps(asdict(c), indent=2) + "\n")


def _append_ledger(record: dict) -> None:
    LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
    with LEDGER_PATH.open("a") as f:
        f.write(json.dumps(record) + "\n")


def record_evidence(candidate_id: str, claim: str, strategy: str, ev: Evidence,
                    archetype: str = "", observed_with: dict | None = None) -> Candidate:
    """Append one observation. Creates the candidate on first sighting;
    corroborates on independent repeats. Called by hooks — zero model turns."""
    _append_ledger({"candidate": candidate_id, **asdict(ev)})

    c = _load(candidate_id) or Candidate(
        id=candidate_id, claim=claim, strategy=strategy,
        archetype=archetype, observed_with=observed_with or {},
    )
    c.evidence.append(asdict(ev))
    if ev.app and ev.app not in c.apps:
        c.apps.append(ev.app)
    if _independent_count(c) >= MIN_EVIDENCE and c.status == "observed":
        c.status = "corroborated"
    _save(c)
    return c


def _independent_count(c: Candidate) -> int:
    """Evidence from different apps counts fully; repeat runs of one route on
    one day are correlated and count once. (Pitch §4/§9: two runs on the same
    app the same afternoon are not independent.)"""
    seen = set()
    for ev in c.evidence:
        day = str(ev.get("ts", ""))[:10]
        seen.add((ev.get("app", ""), ev.get("route", ""), day))
    apps = {ev.get("app", "") for ev in c.evidence}
    # different apps are the strongest independence signal
    return max(len(seen), 0) if len(apps) < 2 else max(len(seen), MIN_EVIDENCE)


def can_promote(candidate_id: str) -> tuple[bool, str]:
    """The mechanical gate. The model cannot argue past this."""
    c = _load(candidate_id)
    if c is None:
        return False, f"no candidate {candidate_id!r}"
    if c.status == "refuted":
        return False, "refuted — see archive"
    n = _independent_count(c)
    if n < MIN_EVIDENCE:
        return False, f"insufficient evidence: {n} independent observation(s), need {MIN_EVIDENCE}"
    if not c.repro:
        return False, "corroborated but no repro — attach a fixture pair or a route that regresses without it"
    return True, f"promotable: {n} independent observations + repro at {c.repro}"


def set_repro(candidate_id: str, repro: str) -> None:
    c = _load(candidate_id)
    if c is None:
        raise KeyError(candidate_id)
    c.repro = repro
    _save(c)


def record_failure(candidate_id: str, detail: str = "") -> str:
    """A confirmed/corroborated strategy failed verification. Two failures
    auto-refute — the self-healing property."""
    c = _load(candidate_id)
    if c is None:
        return "unknown"
    c.failures += 1
    _append_ledger({"candidate": candidate_id, "ts": _now(), "outcome": "fail", "detail": detail})
    if c.failures >= REFUTE_AFTER:
        c.status = "refuted"
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        (ARCHIVE_DIR / f"{c.id}.json").write_text(json.dumps(asdict(c), indent=2) + "\n")
        c.path().unlink(missing_ok=True)
        return "refuted"
    _save(c)
    return c.status


def review() -> list[dict]:
    """Everything /ax-learn needs to render the batched review."""
    out = []
    if CANDIDATES_DIR.exists():
        for p in sorted(CANDIDATES_DIR.glob("*.json")):
            c = Candidate(**json.loads(p.read_text()))
            ok, reason = can_promote(c.id)
            out.append({"id": c.id, "status": c.status, "claim": c.claim,
                        "strategy": c.strategy, "evidence": len(c.evidence),
                        "independent": _independent_count(c),
                        "promotable": ok, "gate": reason})
    return out


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "review"
    if cmd == "review":
        rows = review()
        if not rows:
            print("ledger: no candidates.")
        for r in rows:
            flag = "PROMOTABLE" if r["promotable"] else "held"
            print(f"[{flag:10}] {r['id']}  ({r['status']}, {r['independent']} independent)")
            print(f"             claim: {r['claim']}")
            print(f"             gate:  {r['gate']}")
    elif cmd == "gate" and len(sys.argv) > 2:
        ok, reason = can_promote(sys.argv[2])
        print(("PASS: " if ok else "REFUSED: ") + reason)
        sys.exit(0 if ok else 1)
    else:
        print("usage: python3 -m core.ledger [review | gate <candidate-id>]")
