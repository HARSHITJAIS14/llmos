from lsfg.plan.schema import OPS, parse_plan, plan_schema
from lsfg.plan.validate import substitute, validate_plan
from lsfg.types import AppEntry


class FakeApps:
    def resolve(self, name):
        return AppEntry(name=name, bundle_id="x." + name, path="/x") if name in ("Safari", "WhatsApp", "TextEdit") else None


class FakeSession:
    apps = FakeApps()


def _plan(steps, checks=()):
    return parse_plan({"steps": steps, "checks": list(checks)})


def test_schema_shapes():
    for flavor in ("anyof", "flat"):
        sch = plan_schema(flavor)
        assert sch["required"] == ["steps", "checks"]
    anyof = plan_schema("anyof")["properties"]["steps"]["items"]["anyOf"]
    assert len(anyof) == len(OPS)
    for s in anyof:                                             # every field required: no optional params
        assert set(s["required"]) == set(s["properties"]) and s["additionalProperties"] is False


def test_checks_attach_to_steps():
    p = _plan([{"op": "open_url", "app": "Safari", "url": "https://x.com"}],
              [{"k": "url", "s": 0, "when": "post", "app": "Safari", "pattern": "x\\.com", "g": 0}])
    assert p.steps[0].post[0].kind == "url"


def test_validation_rules():
    ok = _plan([{"op": "open_url", "app": "Safari", "url": "https://x.com"}],
               [{"k": "url", "s": 0, "when": "post", "app": "Safari", "pattern": "x", "g": 0}])
    assert validate_plan(ok, FakeSession()) == []
    bad_scheme = _plan([{"op": "open_url", "app": "Safari", "url": "file:///etc/passwd"}],
                       [{"k": "url", "s": 0, "when": "post", "app": "Safari", "pattern": "x", "g": 0}])
    assert any("scheme" in e for e in validate_plan(bad_scheme, FakeSession()))
    irr = _plan([{"op": "hotkey", "app": "WhatsApp", "keys": "return", "risk": "irreversible"}],
                [{"k": "exists", "s": 0, "when": "post", "app": "WhatsApp", "target": "button~\"x\"", "g": 0}])
    assert any("pre check" in e for e in validate_plan(irr, FakeSession()))
    no_goal = _plan([{"op": "press", "app": "TextEdit", "target": "button:\"OK\"", "button": "left", "risk": "safe"}])
    assert any("proves the goal" in e for e in validate_plan(no_goal, FakeSession()))
    blocked = _plan([{"op": "hotkey", "app": "TextEdit", "keys": "cmd+q", "risk": "safe"}],
                    [{"k": "frontmost", "s": 0, "when": "post", "app": "TextEdit", "g": 0}])
    assert any("blocked" in e for e in validate_plan(blocked, FakeSession()))
    alias = _plan([{"op": "press", "app": "TextEdit", "target": "@e99", "button": "left", "risk": "safe"}],
                  [{"k": "exists", "s": 0, "when": "post", "app": "TextEdit", "target": "@e99", "g": 0}])
    assert any("SCREEN" in e for e in validate_plan(alias, FakeSession(), digest_aliases={"e1"}))
    unknown_app = _plan([{"op": "open_app", "app": "NoSuchApp"}],
                        [{"k": "frontmost", "s": 0, "when": "post", "app": "NoSuchApp", "g": 0}])
    assert any("no installed app" in e for e in validate_plan(unknown_app, FakeSession()))


def test_substitute_formats():
    p = _plan([{"op": "open_url", "app": "Safari", "url": "https://y.com/results?q={s1:url}"}],
              [{"k": "url", "s": 0, "when": "post", "app": "Safari", "pattern": "q={s1:url}|{s1:re}", "g": 0}])
    substitute(p, {"s1": "a b+c"})
    assert p.steps[0].params["url"] == "https://y.com/results?q=a+b%2Bc"
    assert p.steps[0].post[0].params["pattern"].endswith("a\\ b\\+c")


def test_plain_word_apps_need_app_context():
    from lsfg.ax.normalize import fold
    from lsfg.plan.planner import named_as_app, plain_word, names_site

    def hit(name, task):
        return not plain_word(name) or named_as_app(name, f" {fold(task)} ", task)
    assert plain_word("space") and plain_word("mail") and not plain_word("whatsapp")
    assert not hit("space", "open my gmail and search the mail from space by matthew")
    assert not hit("mail", "open my gmail and search the mail from space by matthew")
    assert hit("notes", "open notes and make a list")
    assert hit("notion", "search Notion for the roadmap")
    assert hit("zoom", "join the zoom call")
    assert hit("slack", "tell the team on slack i'm late")
    assert names_site(fold("open my gmail and search the mail from space by matthew"))
    assert names_site(fold("go to news.ycombinator.com")) and not names_site(fold("reply to this"))
