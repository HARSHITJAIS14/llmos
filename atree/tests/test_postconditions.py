"""Postconditions must catch exactly the false-success the old harness
shipped: `folder_name in str(tree)` returning True while the open failed."""
import pytest

from core.postconditions import Postcondition, evaluate


def make_tree(children):
    return {"role": "application", "name": "TestApp", "children": children}


WINDOW_WITH_PICKER_OPEN = make_tree([
    {"role": "window", "name": "Untitled", "children": [
        {"role": "sheet", "name": "Open", "children": [
            # the target path sits in the picker's own text field — the
            # exact configuration that fooled `in str(tree)`
            {"role": "textfield", "name": "path", "value": "/Users/x/LLM_OS"},
        ]},
    ]},
])

WINDOW_ACTUALLY_OPENED = make_tree([
    {"role": "window", "name": "LLM_OS — Visual Studio Code", "children": [
        {"role": "button", "name": "Explorer"},
    ]},
])


def test_old_false_success_is_now_a_failure():
    pc = Postcondition(
        kind="title_matches",
        expect={"pattern": r"LLM_OS"},
        description="workspace opened",
    )
    # substring IS present in the serialized tree...
    assert "LLM_OS" in str(WINDOW_WITH_PICKER_OPEN)
    # ...but the typed check correctly fails: no window titled LLM_OS
    assert not evaluate(pc, WINDOW_WITH_PICKER_OPEN)
    assert evaluate(pc, WINDOW_ACTUALLY_OPENED)


def test_node_exists_and_absent():
    exists = Postcondition(kind="node_exists", expect={"role": "sheet", "name": "Open"})
    absent = Postcondition(kind="node_absent", expect={"role": "sheet"})
    assert evaluate(exists, WINDOW_WITH_PICKER_OPEN)
    assert not evaluate(absent, WINDOW_WITH_PICKER_OPEN)
    assert evaluate(absent, WINDOW_ACTUALLY_OPENED)


def test_value_equals():
    pc = Postcondition(
        kind="value_equals",
        expect={"role": "textfield", "value": "/Users/x/LLM_OS"},
    )
    assert evaluate(pc, WINDOW_WITH_PICKER_OPEN)
    pc_wrong = Postcondition(
        kind="value_equals",
        expect={"role": "textfield", "value": "/Users/x/other"},
    )
    verdict = evaluate(pc_wrong, WINDOW_WITH_PICKER_OPEN)
    assert not verdict and "mismatch" in verdict.detail


def test_scope_restricts_matches():
    pc = Postcondition(
        kind="node_exists",
        expect={"role": "textfield"},
        scope="/window:Untitled[1]/sheet:Open[1]",
    )
    assert evaluate(pc, WINDOW_WITH_PICKER_OPEN)
    pc_wrong_scope = Postcondition(
        kind="node_exists",
        expect={"role": "textfield"},
        scope="/window:LLM_OS",
    )
    assert not evaluate(pc_wrong_scope, WINDOW_WITH_PICKER_OPEN)


def test_name_contains_is_case_insensitive():
    pc = Postcondition(kind="node_exists", expect={"name_contains": "explorer"})
    assert evaluate(pc, WINDOW_ACTUALLY_OPENED)


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        Postcondition(kind="looks_fine_to_me")


def test_json_round_trip():
    pc = Postcondition(kind="node_exists", expect={"role": "sheet"},
                       app="Finder", timeout_ms=5000, description="sheet appears")
    again = Postcondition.from_json(pc.to_json())
    assert again == pc
