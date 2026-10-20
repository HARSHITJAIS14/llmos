"""Engine safety invariants with fakes (no desktop needed)."""
import pytest

import lsfg.engine as eng_mod
import lsfg.session as session_mod
from lsfg.config import Config
from lsfg.plan.schema import parse_plan
from lsfg.verify.evaluate import CheckResult


@pytest.fixture
def engine(monkeypatch, tmp_path):
    monkeypatch.setattr(session_mod, "screen_locked", lambda: False)
    monkeypatch.setattr(eng_mod, "screen_locked", lambda: False)
    monkeypatch.setattr("lsfg.config.TRACE_DIR", tmp_path)
    monkeypatch.setattr("lsfg.trace.trace.config.TRACE_DIR", tmp_path)
    cfg = Config()
    e = eng_mod.Engine(cfg, out=lambda s: None, interactive=False, dialog=False)
    e.session._ctx_cache.clear()
    return e


def _script_checks(monkeypatch, results):
    """wait_checks returns the scripted booleans in order (then True)."""
    seq = list(results)

    def fake(checks, session, timeout):
        ok = seq.pop(0) if seq else True
        return ok, [CheckResult(kind=c.kind, ok=ok, what=c.kind) for c in checks], 1
    monkeypatch.setattr(eng_mod, "wait_checks", fake)


def _plan(op, risk="safe", pre=(), post=({"k": "exists", "app": "TextEdit", "target": "button~\"x\""},)):
    step = {"op": op, "app": "TextEdit", "target": "button~\"x\"", "button": "left", "risk": risk,
            "pre": list(pre), "post": list(post)}
    return parse_plan({"steps": [step]}, source="file")


def test_irreversible_is_never_retried(engine, monkeypatch):
    calls = []
    monkeypatch.setattr(eng_mod.Engine, "_op_press", lambda self, *a: calls.append(1))
    _script_checks(monkeypatch, [True, False, False])          # pre passes, post fails
    plan = _plan("press", risk="irreversible", pre=[{"k": "exists", "app": "TextEdit", "target": "button~\"y\""}])
    res = engine.run("t", plan=plan, yes=True)
    assert res.status == "FAILED" and len(calls) == 1


def test_safe_step_tries_the_other_mode(engine, monkeypatch):
    calls = []
    monkeypatch.setattr(eng_mod.Engine, "_op_press", lambda self, step, ctx, sr, attempt, *a: calls.append(attempt))
    monkeypatch.setattr(eng_mod.Engine, "_explore_fallback", lambda self, *a: False)
    _script_checks(monkeypatch, [False, True])
    res = engine.run("t", plan=_plan("press"), yes=True)
    assert res.status == "SUCCESS" and calls == [0, 1]


def test_failed_pre_check_blocks_the_action(engine, monkeypatch):
    calls = []
    monkeypatch.setattr(eng_mod.Engine, "_op_press", lambda self, *a: calls.append(1))
    monkeypatch.setattr(eng_mod.Engine, "_explore_fallback", lambda self, *a: False)
    _script_checks(monkeypatch, [False])
    plan = _plan("press", pre=[{"k": "exists", "app": "TextEdit", "target": "button~\"y\""}])
    res = engine.run("t", plan=plan)
    assert res.status == "FAILED" and calls == []


def test_confirmation_blocks_when_not_interactive(engine, monkeypatch):
    monkeypatch.setattr(eng_mod.Engine, "_op_press",
                        lambda self, step, ctx, sr, attempt, yes, irr: self._approve(step, ctx, sr, "send", yes))
    _script_checks(monkeypatch, [True])
    plan = _plan("press", risk="irreversible", pre=[{"k": "exists", "app": "TextEdit", "target": "button~\"y\""}])
    res = engine.run("t", plan=plan)
    assert res.status == "BLOCKED_BY_SAFETY"


def test_invalid_plan_never_runs(engine, monkeypatch):
    calls = []
    monkeypatch.setattr(eng_mod.Engine, "_op_open_url", lambda self, *a: calls.append(1))
    plan = parse_plan({"steps": [{"op": "open_url", "app": "Safari", "url": "file:///etc/hosts",
                                  "post": [{"k": "url", "app": "Safari", "pattern": "x"}]}]}, source="file")
    res = engine.run("t", plan=plan)
    assert res.status == "FAILED" and "scheme" in res.reason and calls == []


def test_step_budget(engine, monkeypatch):
    engine.cfg.budgets.steps = 1
    monkeypatch.setattr(eng_mod.Engine, "_op_press", lambda self, *a: None)
    monkeypatch.setattr(eng_mod.Engine, "_explore_fallback", lambda self, *a: False)
    _script_checks(monkeypatch, [False, False])
    res = engine.run("t", plan=_plan("press"))
    assert res.status == "BUDGET"
