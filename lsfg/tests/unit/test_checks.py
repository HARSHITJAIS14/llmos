from lsfg.types import Check
from lsfg.verify.checks import from_json, groups, validate


def test_empty_patterns_are_rejected():                         # reasoning.md D7 (atree bug)
    assert validate(Check("title", "Safari", {"pattern": ""}))
    assert validate(Check("url", "Safari", {"pattern": "   "}))
    assert validate(Check("value", "X", {"target": "focused", "op": "equals", "text": ""}))
    assert validate(Check("text", "X", {"text": "", "region": "window"}))


def test_valid_checks_pass():
    assert validate(Check("url", "Safari", {"pattern": "youtube\\.com"})) == []
    assert validate(Check("value", "X", {"target": "focused", "op": "empty", "text": ""})) == []
    assert validate(Check("state", "X", {"target": "@e1", "state": "checked", "is": True})) == []


def test_bad_regex_and_kinds():
    assert validate(Check("title", "Safari", {"pattern": "("}))
    assert validate(Check("nope", "Safari", {}))
    assert validate(Check("state", "X", {"target": "@e1", "state": "hot", "is": True}))


def test_json_and_groups():
    c = from_json({"k": "url", "app": "Safari", "pattern": "a", "g": 1, "when": "post"})
    assert c.kind == "url" and c.group == 1 and c.params == {"pattern": "a"}
    g = groups([Check("frontmost", "A", {}, 0), Check("url", "A", {"pattern": "x"}, 1), Check("title", "A", {"pattern": "y"}, 1)])
    assert len(g[1]) == 2 and len(g[0]) == 1
