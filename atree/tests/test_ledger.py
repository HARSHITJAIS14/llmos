"""Phase 6 exit check, distilled: n=1 is refused, n=2 independent + repro is
promoted, two failures auto-refute out of context."""
import importlib

import pytest

import core.ledger as ledger_mod


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger_mod, "LEARNINGS_DIR", tmp_path)
    monkeypatch.setattr(ledger_mod, "CANDIDATES_DIR", tmp_path / "candidates")
    monkeypatch.setattr(ledger_mod, "ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr(ledger_mod, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    return ledger_mod


def ev(app, route, day):
    return ledger_mod.Evidence(ts=f"{day}T12:00:00Z", route=route, app=app,
                               outcome="fail-then-pass")


def test_single_observation_is_refused(ledger):
    ledger.record_evidence("axpress-swallowed", "claim", "strategy",
                           ev("Notion", "notion-click", "2026-08-29"))
    ok, reason = ledger.can_promote("axpress-swallowed")
    assert not ok and "insufficient evidence" in reason


def test_correlated_repeats_do_not_corroborate(ledger):
    """Same app, same route, same day, run twice — still one observation."""
    for _ in range(2):
        ledger.record_evidence("ghost-window", "claim", "strategy",
                               ev("Notion", "notion-click", "2026-08-29"))
    ok, reason = ledger.can_promote("ghost-window")
    assert not ok and "insufficient evidence" in reason


def test_independent_evidence_plus_repro_promotes(ledger):
    ledger.record_evidence("axpress-swallowed", "claim", "strategy",
                           ev("Notion", "notion-click", "2026-08-29"))
    ledger.record_evidence("axpress-swallowed", "claim", "strategy",
                           ev("VSCode", "vscode-open", "2026-08-30"))
    ok, reason = ledger.can_promote("axpress-swallowed")
    assert not ok and "no repro" in reason  # corroborated but ungated

    ledger.set_repro("axpress-swallowed", "tests/fixtures/notion_axpress_noop")
    ok, reason = ledger.can_promote("axpress-swallowed")
    assert ok, reason


def test_two_failures_auto_refute(ledger):
    ledger.record_evidence("stale-rule", "claim", "strategy",
                           ev("Notion", "r1", "2026-08-29"))
    assert ledger.record_failure("stale-rule") == "observed"
    assert ledger.record_failure("stale-rule") == "refuted"
    ok, reason = ledger.can_promote("stale-rule")
    assert not ok and "refuted" in reason
    # moved to archive, gone from candidates
    assert not (ledger.CANDIDATES_DIR / "stale-rule.json").exists()
    assert (ledger.ARCHIVE_DIR / "stale-rule.json").exists()


def test_review_reports_gate_status(ledger):
    ledger.record_evidence("c1", "claim", "strategy", ev("Notion", "r", "2026-08-29"))
    rows = ledger.review()
    assert len(rows) == 1
    assert rows[0]["promotable"] is False
