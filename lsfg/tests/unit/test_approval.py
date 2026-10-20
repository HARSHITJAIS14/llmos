"""Approval before irreversible actions: type first, read back, ask, and only then send."""
from types import SimpleNamespace

import pytest

import lsfg.engine as eng_mod
import lsfg.session as session_mod
from lsfg.config import Config
from lsfg.errors import SafetyBlocked, UserAborted
from lsfg.safety.approval import Approval, ask
from lsfg.session import AppCtx
from lsfg.types import AppEntry, Node, Snapshot, Step, StepResult


def _ap():
    return Approval(app="WhatsApp", action="press Return (this sends it)", target='chat "Priya Sharma"',
                    draft="on my way", checks=["✓ title ~ /Priya/"])


def test_card_shows_everything():
    card = _ap().card()
    for part in ("WhatsApp", "press Return", "Priya Sharma", "on my way", "✓ title"):
        assert part in card


def test_yes_no_and_blocked():
    ask(_ap(), yes=True, interactive=False, dialog=False)                             # --yes
    ask(_ap(), yes=False, interactive=True, prompt=lambda q: "y")
    with pytest.raises(UserAborted):
        ask(_ap(), yes=False, interactive=True, prompt=lambda q: "")                # Enter = no
    with pytest.raises(UserAborted):
        ask(_ap(), yes=False, interactive=True, prompt=lambda q: "nope")
    with pytest.raises(SafetyBlocked):
        ask(_ap(), yes=False, interactive=False, dialog=False)                      # nobody to ask


@pytest.fixture
def engine(monkeypatch, tmp_path):
    monkeypatch.setattr(session_mod, "screen_locked", lambda: False)
    monkeypatch.setattr(eng_mod, "screen_locked", lambda: False)
    monkeypatch.setattr("lsfg.trace.trace.config.TRACE_DIR", tmp_path)
    return eng_mod.Engine(Config(), out=lambda s: None, interactive=False, dialog=False)


def _whatsapp_type(engine, monkeypatch, approve: bool):
    events = []
    node = Node(alias="e9", key=(0, 9), ref=object(), role="textfield", name="Type a message")
    snap = Snapshot(pid=123, bundle_id="net.whatsapp.WhatsApp", app_name="WhatsApp", framework="catalyst",
                    stack="native")
    snap.nodes[node.alias] = node
    snap.order.append(node.alias)
    monkeypatch.setattr(eng_mod.Engine, "_target", lambda self, step, ctx, field="target": (node, snap))
    monkeypatch.setattr(eng_mod.Engine, "_focus_field", lambda self, n, pid: None)
    monkeypatch.setattr(eng_mod.focus, "activate", lambda pid, window_ref=None, timeout=0.4: True)
    monkeypatch.setattr(eng_mod.focus, "activation_blocked", lambda: False)
    monkeypatch.setattr(eng_mod.semantic, "select_all", lambda n: 0)
    monkeypatch.setattr(eng_mod.raw, "attr", lambda ref, name, timeout=0.5: (0, "on my way"))
    monkeypatch.setattr(eng_mod.clipboard, "paste_text",
                        lambda text, pid, landed=None, timeout=0.8: events.append(("paste", text)) or True)
    monkeypatch.setattr(eng_mod.keys, "press", lambda k, pid: events.append(("key", k)))

    def fake_ask(ap, **kw):
        events.append(("approve?", ap.draft, ap.action))
        if not approve:
            raise UserAborted("no")
    monkeypatch.setattr(eng_mod.approval, "ask", fake_ask)
    ctx = AppCtx(entry=AppEntry(name="WhatsApp", bundle_id="net.whatsapp.WhatsApp", path="/x"),
                 framework="catalyst", stack="native", pid=123)
    step = Step(index=0, op="type", app="WhatsApp",
                params={"target": "focused", "text": "on my way", "mode": "replace", "submit": True})
    sr = StepResult(index=0, op="type", status="FAIL")
    return events, lambda: engine._op_type(step, ctx, sr, 0, False, True)


def test_types_first_then_asks_then_sends(engine, monkeypatch):
    events, run = _whatsapp_type(engine, monkeypatch, approve=True)
    run()
    assert [e[0] for e in events] == ["paste", "approve?", "key"]
    assert events[1][1] == "on my way" and "sends" in events[1][2]
    assert events[2] == ("key", "return")


def test_declining_never_sends(engine, monkeypatch):
    events, run = _whatsapp_type(engine, monkeypatch, approve=False)
    with pytest.raises(UserAborted):
        run()
    assert ("key", "return") not in events
