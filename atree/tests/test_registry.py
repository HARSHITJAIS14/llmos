"""Registry: deposits, recall levels, failure-driven invalidation, denylist,
and the selectors-not-content privacy rule."""
import pytest

from core import recall, registry


@pytest.fixture
def con(tmp_path):
    return registry.connect(tmp_path / "test.db")


def seed_notion(con):
    app_id = registry.get_or_create_app(con, "Notion", archetype="electron")
    el_id = registry.upsert_element(
        con, app_id, identity_path="/webarea:notion-app[1]/button:Library[1]",
        role="button", name="Library", reach_strategy="keyboard-macro",
    )
    return app_id, el_id


def test_deposit_and_element_recall(con):
    app_id, _ = seed_notion(con)
    hits = registry.find_elements(con, "Notion", name_like="Library")
    assert len(hits) == 1
    assert hits[0]["reach_strategy"] == "keyboard-macro"


def test_recall_levels(con):
    app_id, _ = seed_notion(con)

    # L2: app mapped, no route yet
    r = recall.recall("click the Library tab", "Notion", con=con)
    assert r["level"] == "L2"
    assert r["elements"][0]["reach_strategy"] == "keyboard-macro"

    # L1 after a route is saved
    registry.save_route(con, app_id, "click the Library tab",
                        steps=[{"cmd": "press cmd+k"}], turns=1)
    r = recall.recall("click the Library tab", "Notion", con=con)
    assert r["level"] == "L1"
    assert r["steps"] == [{"cmd": "press cmd+k"}]

    # L3: known app, unknown task keywords
    r = recall.recall("zzz qqq xxx", "Notion", con=con)
    assert r["level"] == "L3"

    # miss: unknown app
    r = recall.recall("anything", "UnknownApp", con=con)
    assert r["level"] == "miss"


def test_failed_outcome_erodes_confidence_to_invalidation(con):
    _, el_id = seed_notion(con)
    before = registry.find_elements(con, "Notion")
    assert before, "seed element should be above the confidence floor"

    for _ in range(8):
        registry.record_outcome(con, "fail", element_id=el_id)

    after = registry.find_elements(con, "Notion")
    assert not after, "repeatedly failing element must fall below the floor"


def test_pass_outcomes_recover_confidence(con):
    _, el_id = seed_notion(con)
    for _ in range(3):
        registry.record_outcome(con, "pass", element_id=el_id)
    hits = registry.find_elements(con, "Notion")
    assert hits and hits[0]["confidence"] > 0.6


def test_denylist_refuses_deposits(con):
    assert registry.get_or_create_app(con, "Messages") is None
    assert registry.get_or_create_app(con, "anything", bundle_id="com.apple.MobileSMS") is None
    assert registry.denied("1Password")


def test_content_names_are_never_stored_verbatim(con):
    app_id, _ = seed_notion(con)
    registry.upsert_element(
        con, app_id, identity_path="/webarea:x[1]/row:secret[1]",
        role="button", name="Vivek CSE B311", is_content=True,
    )
    row = con.execute(
        "SELECT name_pattern FROM elements WHERE identity_path LIKE '%secret%'"
    ).fetchone()
    assert "Vivek" not in row["name_pattern"]
    assert row["name_pattern"].startswith("content:")


def test_bulk_invalidation(con):
    app_id, el_id = seed_notion(con)
    registry.record_outcome(con, "pass", element_id=el_id)
    assert registry.invalidate_app(con, app_id) >= 1
    row = con.execute("SELECT last_confirmed FROM elements WHERE id=?", (el_id,)).fetchone()
    assert row["last_confirmed"] is None


def test_signature_normalization():
    a = registry.normalize_signature('Send WhatsApp message to "Alice" saying "hi"')
    b = registry.normalize_signature("send   whatsapp message to 'Bob' saying 'yo'")
    assert a == b
