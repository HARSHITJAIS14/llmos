import re

from lsfg.plan.compile import compile_route
from lsfg.plan.schema import parse_plan
from lsfg.router import RE_OPEN, RE_OPEN_SITE_IN, RE_SEARCH, normalize_task, site_info


def _steps(steps):
    return parse_plan({"steps": steps}).steps


def test_compile_type_literal_becomes_slot():
    steps = _steps([
        {"op": "open_app", "app": "Spotify", "post": [{"k": "frontmost", "app": "Spotify"}]},
        {"op": "type", "app": "Spotify", "target": "focused", "text": "get lucky", "mode": "replace", "submit": True,
         "risk": "safe", "post": []},
        {"op": "choose", "app": "Spotify", "among": "list", "want": "the song get lucky", "then": "double",
         "risk": "safe", "post": [{"k": "title", "app": "Spotify", "pattern": "get lucky"}]},
    ])
    c = compile_route("play get lucky on spotify", steps, {})
    assert c is not None
    assert c["template"] == "play {s1} on spotify"
    m = re.fullmatch(c["regex"], normalize_task("Play Blinding Lights on Spotify."))
    assert m and m.group("s1") == "blinding lights"
    assert c["plan"]["steps"][1]["text"] == "{s1}"


def test_compile_refuses_unmatched_literal():
    steps = _steps([{"op": "type", "app": "Spotify", "target": "focused", "text": "Get Lucky Daft Punk",
                     "mode": "replace", "submit": False, "risk": "safe", "post": []}])
    assert compile_route("play get lucky", steps, {}) is None


def test_compile_refuses_unbound_alias():
    steps = _steps([{"op": "press", "app": "X", "target": "@e5", "button": "left", "risk": "safe", "post": []}])
    assert compile_route("press the thing", steps, {}) is None


def test_router_regexes():
    m = RE_OPEN_SITE_IN.match(normalize_task("Open YouTube on Safari!"))
    assert m and m.group("site") == "youtube" and m.group("browser") == "safari"
    m = RE_SEARCH.match(normalize_task("search lofi hip hop on youtube"))
    assert m and m.group("q") == "lofi hip hop" and m.group("site") == "youtube"
    assert RE_OPEN.match("open notion").group("name") == "notion"
    assert site_info("youtube")[0] == "https://www.youtube.com"
    assert site_info("wikipedia.org")[0] == "https://wikipedia.org"
    assert site_info("not a site") is None
