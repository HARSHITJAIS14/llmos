"""The memory facade: routes + profiles + the learning step after a successful task."""
from __future__ import annotations

import time
from pathlib import Path

from .. import config
from ..plan.compile import compile_route
from ..safety import policy
from . import db
from .profiles import Profiles
from .routes import Routes


class Memory:
    def __init__(self, path: Path | None = None) -> None:
        self.con = db.connect(path or config.DB_PATH)
        self.profiles = Profiles(self.con)
        self.routes = Routes(self.con)

    def learn(self, task: str, plan, result, session, slots: dict) -> None:
        steps = session.bindings.get("executed_steps") or plan.steps
        bundles = []
        versions = {}
        for s in steps:
            if s.app:
                try:
                    ctx = session.ctx(s.app)
                except Exception:
                    continue
                if policy.denied(ctx.bundle_id, session.cfg.privacy.extra_denylist):
                    return                                          # private apps never get routes
                if ctx.bundle_id not in bundles:
                    bundles.append(ctx.bundle_id)
                    versions[ctx.bundle_id] = ctx.entry.version
        self.con.execute("INSERT INTO outcomes(ts, task_hash, route_id, status, total_ms, opus_calls, jev_calls, "
                         "tokens_in, tokens_out, cost_usd, trace_path) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                         (time.time(), str(hash(task)), result.route_id, result.status, result.total_ms,
                          result.opus_calls, result.jev_calls, result.tokens.get("opus_in", 0),
                          result.tokens.get("opus_out", 0), result.cost_usd, result.trace_path))
        self.con.commit()
        alias_table = session.bindings.get("alias_selectors", {})
        if result.route_id is not None:
            self.routes.record(result.route_id, ok=True, ms=result.total_ms)
            self.routes.mark_stale_if_version_changed(result.route_id, versions)
            if any(sr.recovery for sr in result.steps):              # self-healed: keep the fixed steps
                compiled = compile_route(task, steps, alias_table)
                if compiled:
                    self.routes.patch(result.route_id, compiled)
            return
        compiled = compile_route(task, steps, alias_table)
        if compiled is None:
            session.tracer.event("learn", saved=False, why="a literal is not a clean span of the task")
            return
        rid = self.routes.save(compiled, bundles, versions, result.trace_path, result.total_ms)
        session.tracer.event("learn", saved=True, route=rid, template=compiled["template"])

    def forget(self, routes: bool = True, profiles: bool = True) -> None:
        if routes:
            self.routes.forget()
        if profiles:
            self.profiles.forget()
