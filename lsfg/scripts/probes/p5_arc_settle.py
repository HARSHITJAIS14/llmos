"""Shows arc-cua's settle probe never stabilizes on an idle UI (ids come from repr(ref)).
Result on 2026-09-30: signatures equal False; ids reused 0/6; two full observes differ.
Needs the arc-cua repo next to lsfg. Read-only."""
import pathlib
import sys

ARC = pathlib.Path(__file__).resolve().parents[3] / "arc-cua" / "src"
sys.path.insert(0, str(ARC))
from arc_cua.backends.macos_hybrid import MacOSHybridBackend  # noqa: E402

b = MacOSHybridBackend()
s1, s2 = b.settle_probe(), b.settle_probe()
ids1, ids2 = [r[0] for r in s1[4]], [r[0] for r in s2[4]]
print("settle signature equal on idle UI:", s1 == s2)
print("element ids reused:", sum(1 for x, y in zip(ids1, ids2) if x == y), "/", len(ids1))
o1, o2 = b.ax.observe(), b.ax.observe()
print("full observe revisions equal on idle UI:", o1.revision == o2.revision, "| elements:", len(o1.elements))
