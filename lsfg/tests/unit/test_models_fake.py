"""Planner and JEV with fake transports."""
import json
from types import SimpleNamespace

import httpx

from lsfg.config import Config
from lsfg.decide.jev import JevClient, validate_choice
from lsfg.plan.planner import Planner
from lsfg.session import Counters, NullTracer
from lsfg.types import Node, Snapshot


class FakeMessages:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        text = json.dumps(self.replies.pop(0))
        usage = SimpleNamespace(input_tokens=100, output_tokens=50, cache_read_input_tokens=900,
                                cache_creation_input_tokens=0, cache_creation=None)
        return SimpleNamespace(content=[SimpleNamespace(type="thinking", thinking="..."),
                                        SimpleNamespace(type="text", text=text)], usage=usage)


class FakeApps:
    aliases = {}

    def resolve(self, name):
        from lsfg.types import AppEntry
        return AppEntry(name=name, bundle_id="com.apple.Safari", path="/Applications/Safari.app") if name == "Safari" else None

    def _all(self):
        return []

    entries = []

    def by_bundle(self, bid):
        return self.resolve("Safari") if bid == "com.apple.Safari" else None


class FakeSession:
    def __init__(self):
        self.apps = FakeApps()
        self.counters = Counters()
        self.tracer = NullTracer()
        self.bindings = {}
        self.last = {}

    def profile(self, b):
        return {}


def test_planner_repairs_once(monkeypatch):
    good = {"steps": [{"op": "open_url", "app": "Safari", "url": "https://www.youtube.com"}],
            "checks": [{"k": "url", "s": 0, "when": "post", "app": "Safari", "pattern": "youtube", "g": 0}]}
    bad = {"steps": [{"op": "open_url", "app": "Safari", "url": "https://www.youtube.com"}],
           "checks": [{"k": "url", "s": 0, "when": "post", "app": "Safari", "pattern": "", "g": 0}]}
    msgs = FakeMessages([bad, good])
    p = Planner(Config(), FakeSession(), client=SimpleNamespace(messages=msgs))
    monkeypatch.setattr(p, "_contexts", lambda task, routes: [])
    plan = p.plan("open youtube on safari")
    assert plan.steps[0].params["url"] == "https://www.youtube.com"
    assert len(msgs.calls) == 2
    assert "ERRORS" in msgs.calls[1]["messages"][0]["content"]
    kw = msgs.calls[0]
    assert kw["model"] == "claude-opus-5-5"
    assert kw["output_config"]["effort"] == "low" and kw["output_config"]["format"]["type"] == "json_schema"
    assert "thinking" not in kw                               # Opus 5.5: never send thinking
    assert kw["system"][0]["cache_control"]["ttl"] == "1h"
    assert p.session.counters.opus_calls == 2 and p.session.counters.tokens["opus_cached"] == 1800


def _node(alias, name):
    n = Node(alias=alias, key=(0, int(alias[1:])), ref=None, role="button", name=name)
    n.caps_preset = True
    n.caps["Click"] = True
    return n


def _jev(answer):
    def handler(request):
        body = json.loads(request.content)
        assert "elements" not in body["state"]               # candidates live only in criteria
        return httpx.Response(200, json={"model": "jev-1.13.0", "answers": {"target": answer},
                                         "usage": {"input_tokens": 500, "output_tokens": 50}})
    cfg = Config()
    cfg.typesafe_api_key = "k"
    return JevClient(cfg, client=httpx.Client(transport=httpx.MockTransport(handler)))


def _choose(answer):
    snap = Snapshot(pid=0, bundle_id="", app_name="WhatsApp", framework="catalyst", stack="native")
    cands = [_node("e1", "Priya Sharma"), _node("e2", "Priya (Work)")]
    for c in cands:
        snap.nodes[c.alias] = c
        snap.order.append(c.alias)
    s = FakeSession()
    ctx = SimpleNamespace(name="WhatsApp")
    return _jev(answer).choose(s, ctx, snap, cands, want="Priya Sharma", step_goal="open chat"), s


def test_jev_accepts_confident_pick():
    node, s = _choose({"choice": "e1", "confidence": 0.9, "probabilities": {"e1": 0.9, "e2": 0.08, "NONE": 0.02}})
    assert node.alias == "e1" and s.counters.jev_calls == 1


def test_jev_rejects_low_margin_and_none():
    node, _ = _choose({"choice": "e1", "confidence": 0.55, "probabilities": {"e1": 0.55, "e2": 0.44, "NONE": 0.01}})
    assert node is None
    node, _ = _choose({"choice": "NONE", "confidence": 0.9, "probabilities": {"e1": 0.05, "e2": 0.05, "NONE": 0.9}})
    assert node is None


def test_validate_choice():
    ids = {"a", "b"}
    assert validate_choice({"choice": "a", "confidence": 0.7, "probabilities": {"a": 0.7, "b": 0.3}}, ids)
    assert not validate_choice({"choice": "a", "confidence": 0.7, "probabilities": {"a": 0.7}}, ids)
    assert not validate_choice({"choice": "b", "confidence": 0.7, "probabilities": {"a": 0.7, "b": 0.3}}, ids)
