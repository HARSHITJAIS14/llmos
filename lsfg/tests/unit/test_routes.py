from types import SimpleNamespace

from lsfg.memory import db
from lsfg.memory.routes import Routes
from lsfg.plan.compile import compile_route
from lsfg.plan.schema import parse_plan


class Apps:
    def by_bundle(self, b):
        return SimpleNamespace(name="Spotify")


def _routes(tmp_path):
    return Routes(db.connect(tmp_path / "t.db"))


def test_save_match_promote_disable(tmp_path):
    steps = parse_plan({"steps": [
        {"op": "type", "app": "Spotify", "target": "focused", "text": "get lucky", "mode": "replace",
         "submit": True, "risk": "safe", "post": []}]}).steps
    c = compile_route("play get lucky on spotify", steps, {})
    r = _routes(tmp_path)
    rid = r.save(c, ["com.spotify.client"], {"com.spotify.client": "1.2"}, "trace", 1200)
    session = SimpleNamespace(apps=Apps())
    hit = r.match("Play Blinding Lights on Spotify", session)
    assert hit is not None
    route_id, plan, slots = hit
    assert route_id == rid and slots == {"s1": "blinding lights"}
    assert plan.steps[0].params["text"] == "blinding lights"
    assert r.match("play something else on youtube", session) is None
    r.record(rid, ok=True, ms=900)
    assert r.status_line(rid).startswith("trusted")
    r.record(rid, ok=False, ms=0)
    r.record(rid, ok=False, ms=0)
    assert r.status_line(rid).startswith("disabled")
    assert r.match("play x on spotify", session) is None
