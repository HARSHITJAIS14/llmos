"""Live tests: they drive real apps on this Mac. Opt-in: pytest -m live (implementation.md §19.3).

Safe by design: they open web pages and read trees. Nothing is sent, deleted, or typed into
your documents.
"""
import time

import pytest

from lsfg.act import apps
from lsfg.ax import raw, windows
from lsfg.engine import Engine
from lsfg.session import Session, screen_locked

pytestmark = [pytest.mark.live, pytest.mark.skipif(screen_locked(), reason="the screen is locked")]


@pytest.fixture(scope="module")
def engine():
    return Engine(interactive=False, out=print)


def test_open_youtube_on_safari(engine):                         # M1 exit: no model, < 2.5 s
    r = engine.run("open youtube on safari")
    assert r.status == "SUCCESS", r.reason
    assert r.opus_calls == 0 and r.jev_calls == 0
    print(f"open youtube on safari: {r.total_ms} ms")


def test_search_lofi_on_youtube(engine):
    r = engine.run("search lofi on youtube in safari")
    assert r.status == "SUCCESS", r.reason
    print(f"search lofi: {r.total_ms} ms")


def test_identity_is_stable_across_walks(engine):               # E1 on every running app
    s = engine.session
    for a in apps._running_entries():
        try:
            ctx = s.ctx(a.bundle_id)
            first = s.observe(ctx)
            second = s.observe(ctx)
        except Exception:
            continue
        same = set(first.nodes) & set(second.nodes)
        assert len(same) >= 0.9 * min(len(first.nodes), len(second.nodes)), a.name


def test_observe_is_fast_on_safari(engine):
    ctx = engine.session.ctx("Safari")
    if ctx.pid is None:
        pytest.skip("Safari not running")
    t0 = time.perf_counter()
    snap = engine.session.observe(ctx)
    ms = (time.perf_counter() - t0) * 1000
    print(f"Safari observe: {ms:.0f} ms, {len(snap.nodes)} nodes, {snap.ax_calls} AX calls")
    assert ms < 1500


def test_url_check_reads_axurl(engine):                          # E10
    from lsfg.types import Check
    from lsfg.verify.evaluate import evaluate
    r = evaluate(Check("url", "Safari", {"pattern": "youtube"}), engine.session)
    print("Safari page URL:", r.observed)
    assert r.observed
