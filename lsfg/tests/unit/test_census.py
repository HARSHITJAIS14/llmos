"""Law checks on the 24-app census (implementation.md §19.2). Numbers are per capture."""
from conftest import census

from lsfg import testing
from lsfg.ax import caps
from lsfg.ax.classify import classify_tree
from lsfg.ax.labels import label
from lsfg.ax.windows import census_ghost
from lsfg.plan.cards import _profiles
from lsfg.resolve.resolver import resolve_in
from lsfg.resolve.selector import parse

TRUTH = {"antigravity_ide": "chromium-family", "claude": "chromium-family", "discord": "chromium-family",
         "notion": "chromium-family", "brave_browser": "chromium-family", "google_chrome": "chromium-family",
         "firefox": "gecko", "yt_music": "wkwebview", "telegram": "opaque", "obs": "qt",
         "microsoft_word": "custom", "zoom_us": "hybrid"}


@census
def test_ghost_predicate_matches_codex():                       # LAW-WIN-1: 130/161
    total = ghosts = 0
    for app in testing.APPS:
        for w in testing.windows_listing(app):
            total += 1
            ghosts += census_ghost(w)
    assert (ghosts, total) == (130, 161)


@census
def test_appkit_textfield_labels_are_not_typeable():            # LAW-ACT-8
    finder = testing.load_snapshot("finder", "full")
    fields = [n for n in finder.iter() if n.role == "textfield"]
    assert len(fields) > 700
    assert sum(caps.typeable(n, "native") for n in fields) == 0
    for app in ("calendar", "vlc"):
        s = testing.load_snapshot(app, "full")
        fields = [n for n in s.iter() if n.role == "textfield"]
        assert fields and all(caps.typeable(n, "native") for n in fields)


@census
def test_toggle_biconditional():                                # LAW-ACT-2
    for app in ("calendar", "music", "firefox", "notion"):
        s = testing.load_snapshot(app, "forced") or testing.load_snapshot(app, "full")
        for n in s.iter():
            if caps.cap(n, "Toggle"):
                assert n.role in ("checkbox", "radiobutton", "switch"), (app, n.role)


@census
def test_classify_matches_replay_24_of_24():                    # playbook CLASSIFY
    ok = 0
    for app in testing.APPS:
        d = testing.raw_capture(app, "full")
        sk = testing.raw_capture(app, "skeleton")
        c = classify_tree(d["tree"], sk["tree"] if sk else None, d.get("ref_count", 1))
        ok += c == TRUTH.get(app, "native")
    assert ok == 24


@census
def test_whatsapp_chat_rows_label_from_value():                 # LAW-TXT-5
    s = testing.load_snapshot("whatsapp", "full")
    rows = [n for n in s.iter() if n.role == "button" and isinstance(n.value, str) and n.value.startswith("‎")
            and "," in n.value]
    assert rows
    for r in rows:
        assert label(r, s) and "," not in label(r, s)


@census
def test_codex_anchors_resolve_in_safari():                     # every Safari anchor finds its node
    s = testing.load_snapshot("safari", "full")
    anchors = _profiles()["com.apple.Safari"]["anchors"]
    found = sum(resolve_in(parse(a["selector"]), s).kind in ("FOUND", "AMBIGUOUS") for a in anchors)
    assert found == len(anchors)


@census
def test_ambiguous_is_never_first_match():                      # LAW-ID-6/7
    s = testing.load_snapshot("calendar", "full")
    from collections import Counter
    counts = Counter((n.role, label(n, s)) for n in s.iter() if label(n, s) and not n.zero_area)
    (role, text), n = counts.most_common(1)[0]
    assert n > 1
    sel = parse(f'{role}:"{text}"')
    assert resolve_in(sel, s).kind == "AMBIGUOUS"
    assert resolve_in(parse(f'{role}:"{text}"[0]'), s).kind == "FOUND"


@census
def test_selector_from_node_round_trips():                      # §8.1 alias → stored selector
    from lsfg.resolve.selector import fmt, from_node
    for app in ("safari", "whatsapp", "calendar", "textedit"):
        s = testing.load_snapshot(app, "full")
        checked = 0
        for n in s.iter():
            if not caps.clickable(n, "") or n.zero_area or "hidden" in n.states:
                continue
            sel = from_node(n, s)
            r = resolve_in(parse(fmt(sel)), s)
            assert r.kind == "FOUND" and r.node.alias == n.alias, (app, fmt(sel), r.kind)
            checked += 1
        assert checked > 0
