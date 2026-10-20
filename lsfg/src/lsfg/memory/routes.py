"""Routes: saved plans with slots that replay with no model (implementation.md §14.3–14.6).

Matching is a full regex match (never fuzzy: a wrong-route replay is worse than a planner call).
Every replayed step is still verified. candidate → trusted after 2 passes; 2 failures in a row
→ disabled; a new app version → stale.
"""
from __future__ import annotations

import json
import platform
import re
import sqlite3
import statistics
import time

from ..plan.schema import parse_plan
from ..plan.validate import substitute
from ..router import normalize_task
from ..types import Plan


class Routes:
    def __init__(self, con: sqlite3.Connection) -> None:
        self.con = con

    # ------------------------------------------------------------------ lookup
    def _rows(self, statuses=("candidate", "trusted", "stale")):
        q = f"SELECT * FROM routes WHERE status IN ({','.join('?' * len(statuses))}) ORDER BY literal_len DESC"
        return self.con.execute(q, statuses).fetchall()

    def match(self, task: str, session) -> tuple[int, Plan, dict] | None:
        t = normalize_task(task)
        hits: list[tuple[int, sqlite3.Row, dict]] = []
        for row in self._rows():
            regexes = [row["regex"]] + [a["regex"] for a in self.con.execute(
                "SELECT regex FROM route_aliases WHERE route_id=?", (row["id"],)).fetchall()]
            for rx in regexes:
                m = re.fullmatch(rx, t)
                if m:
                    hits.append((row["literal_len"] or 0, row, m.groupdict()))
                    break
        if not hits:
            return None
        hits.sort(key=lambda h: -h[0])
        if len(hits) > 1 and hits[0][0] == hits[1][0] and hits[0][1]["id"] != hits[1][1]["id"]:
            return None                                          # a tie: let the planner pick (it sees ROUTES)
        _, row, slots = hits[0]
        for bid in json.loads(row["bundle_ids"] or "[]"):
            if session.apps.by_bundle(bid) is None:
                return None                                      # an app the route needs is gone
        plan = self.plan_for(row["id"], slots)
        return (row["id"], plan, slots) if plan is not None else None

    def plan_for(self, route_id: int, slots: dict) -> Plan | None:
        row = self.con.execute("SELECT * FROM routes WHERE id=?", (route_id,)).fetchone()
        if row is None:
            return None
        plan = parse_plan(json.loads(row["plan_json"]), source=f"route:{route_id}")
        return substitute(plan, {k: str(v) for k, v in slots.items()})

    def for_task(self, task: str, session) -> list[dict]:
        """Routes whose apps the task mentions, for the planner's ROUTES line (paraphrase matching)."""
        t = f" {normalize_task(task)} "
        out = []
        for row in self._rows():
            bids = json.loads(row["bundle_ids"] or "[]")
            names = [e.name.lower() for e in (session.apps.by_bundle(b) for b in bids) if e]
            if any(f" {n} " in t for n in names) or not names:
                out.append({"id": row["id"], "template": row["template"], "runs": row["runs"],
                            "passes": row["passes"], "bundle_ids": bids})
        return out[:10]

    def status_line(self, route_id: int) -> str:
        row = self.con.execute("SELECT status, runs, passes FROM routes WHERE id=?", (route_id,)).fetchone()
        return f"{row['status']}, {row['passes']}/{row['runs']}" if row else "?"

    # ------------------------------------------------------------------ write
    def save(self, compiled: dict, bundle_ids: list[str], versions: dict, source_trace: str, ms: int) -> int:
        now = time.time()
        existing = self.con.execute("SELECT * FROM routes WHERE template=?", (compiled["template"],)).fetchone()
        if existing is not None:
            self.record(existing["id"], ok=True, ms=ms)
            return existing["id"]
        cur = self.con.execute(
            "INSERT INTO routes(bundle_ids, template, regex, slots_json, plan_json, status, runs, passes, "
            "median_ms, app_versions_json, os_version, created_at, last_pass_at, source_trace, literal_len) "
            "VALUES(?,?,?,?,?,'candidate',1,1,?,?,?,?,?,?,?)",
            (json.dumps(bundle_ids), compiled["template"], compiled["regex"], json.dumps(compiled["slots"]),
             json.dumps(compiled["plan"]), ms, json.dumps(versions), platform.mac_ver()[0], now, now,
             source_trace, compiled["literal_len"]))
        self.con.commit()
        return int(cur.lastrowid)

    def add_alias(self, route_id: int, template: str, regex: str) -> None:
        self.con.execute("INSERT INTO route_aliases(route_id, template, regex) VALUES(?,?,?)", (route_id, template, regex))
        self.con.commit()

    def record(self, route_id: int, *, ok: bool, ms: int) -> None:
        row = self.con.execute("SELECT * FROM routes WHERE id=?", (route_id,)).fetchone()
        if row is None:
            return
        runs, passes = row["runs"] + 1, row["passes"] + (1 if ok else 0)
        fails = row["fails"] + (0 if ok else 1)
        consec = 0 if ok else row["consecutive_fails"] + 1
        status = row["status"]
        if ok and passes >= 2 and status in ("candidate", "stale"):
            status = "trusted"
        if consec >= 2:
            status = "disabled"
        median = row["median_ms"] or ms
        if ok:
            median = int(statistics.median([median, ms]))
        self.con.execute("UPDATE routes SET runs=?, passes=?, fails=?, consecutive_fails=?, status=?, median_ms=?, "
                         "last_pass_at=COALESCE(?, last_pass_at) WHERE id=?",
                         (runs, passes, fails, consec, status, median, time.time() if ok else None, route_id))
        self.con.commit()

    def patch(self, route_id: int, compiled: dict) -> None:
        self.con.execute("UPDATE routes SET prev_plan_json=plan_json, plan_json=?, version=version+1 WHERE id=?",
                         (json.dumps(compiled["plan"]), route_id))
        self.con.commit()

    def mark_stale_if_version_changed(self, route_id: int, versions: dict) -> None:
        row = self.con.execute("SELECT app_versions_json, status FROM routes WHERE id=?", (route_id,)).fetchone()
        if row is None:
            return
        old = json.loads(row["app_versions_json"] or "{}")
        if any(old.get(b) and v and old.get(b) != v for b, v in versions.items()) and row["status"] != "disabled":
            self.con.execute("UPDATE routes SET status='stale', app_versions_json=? WHERE id=?",
                             (json.dumps(versions), route_id))
            self.con.commit()

    def forget(self) -> None:
        self.con.execute("DELETE FROM route_aliases")
        self.con.execute("DELETE FROM routes")
        self.con.commit()

    # ------------------------------------------------------------------ CLI
    def cli(self, action: str, rid: str | None) -> int:
        if action == "list":
            rows = self.con.execute("SELECT * FROM routes ORDER BY id").fetchall()
            if not rows:
                print("no routes yet (they are saved after a planner task succeeds)")
            for r in rows:
                print(f"r{r['id']:<4} {r['status']:<9} {r['passes']}/{r['runs']:<3} {r['median_ms'] or 0:>6} ms  {r['template']}")
            return 0
        if rid is None:
            print("usage: lsfg routes show|rm|disable|enable ID")
            return 1
        route_id = int(str(rid).lstrip("r"))
        if action == "show":
            r = self.con.execute("SELECT * FROM routes WHERE id=?", (route_id,)).fetchone()
            if r is None:
                print("no such route")
                return 1
            print(json.dumps({k: r[k] for k in r.keys() if k != "plan_json"}, indent=1, default=str))
            print(json.dumps(json.loads(r["plan_json"]), indent=1))
            return 0
        if action == "rm":
            self.con.execute("DELETE FROM routes WHERE id=?", (route_id,))
        elif action in ("disable", "enable"):
            self.con.execute("UPDATE routes SET status=?, consecutive_fails=0 WHERE id=?",
                             ("disabled" if action == "disable" else "candidate", route_id))
        else:
            print(f"unknown action {action}")
            return 1
        self.con.commit()
        print(f"r{route_id}: {action} done")
        return 0
