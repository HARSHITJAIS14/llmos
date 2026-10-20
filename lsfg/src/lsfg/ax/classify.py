"""Framework from the bundle (file checks only), confirmed by the tree (implementation.md §6.7).

Stacks: native (AppKit/SwiftUI/Catalyst/iWork/custom C++), web (Electron, CEF, Chromium,
Gecko, WKWebView apps, and browsers for their page content), qt, opaque (decided at runtime).
"""
from __future__ import annotations

import plistlib
from functools import lru_cache
from pathlib import Path

CHROMIUM_BUNDLES = frozenset({
    "com.google.Chrome", "com.google.Chrome.beta", "com.google.Chrome.canary", "org.chromium.Chromium",
    "com.brave.Browser", "com.microsoft.edgemac", "company.thebrowser.Browser", "com.vivaldi.Vivaldi",
    "com.operasoftware.Opera",
})
BROWSERS = CHROMIUM_BUNDLES | {"com.apple.Safari", "com.apple.SafariTechnologyPreview", "org.mozilla.firefox"}
CUSTOM_CPP = frozenset({"com.microsoft.Word", "com.microsoft.Excel", "com.microsoft.Powerpoint",
                        "com.microsoft.Outlook", "us.zoom.xos"})
WEB_FRAMEWORKS = frozenset({"electron", "cef", "chromium_browser", "gecko", "wkwebview_webapp", "webkit_native"})


@lru_cache(maxsize=256)
def bundle_framework(bundle_path: str, bundle_id: str) -> str:
    root = Path(bundle_path) if bundle_path else None
    fw = root / "Contents" / "Frameworks" if root else None
    bid = bundle_id or ""
    try:
        if fw and (fw / "Electron Framework.framework").exists():
            return "electron"
        if fw and (fw / "Chromium Embedded Framework.framework").exists():
            return "cef"
        if bid in CHROMIUM_BUNDLES or (fw and any(
                any(k in p.name for k in ("Chrome", "Chromium", "Brave", "Edge", "Vivaldi", "Opera"))
                for p in fw.glob("* Framework.framework"))):
            return "chromium_browser"
        if root and ((root / "Contents" / "MacOS" / "XUL").exists() or (fw and (fw / "XUL.framework").exists())):
            return "gecko"
        if fw and (list(fw.glob("QtCore.framework")) or list(fw.glob("libQt*Core*.dylib"))):
            return "qt"
    except OSError:
        pass
    if bid.startswith("com.apple.Safari.WebApp"):
        return "wkwebview_webapp"
    if bid in ("com.apple.Safari", "com.apple.SafariTechnologyPreview"):
        return "webkit_native"
    if bid.startswith("com.apple.iWork."):
        return "iwork"
    if bid in CUSTOM_CPP:
        return "custom_cpp"
    if root and _is_catalyst(root):
        return "catalyst"
    return "appkit"


def _is_catalyst(root: Path) -> bool:
    try:
        with open(root / "Contents" / "Info.plist", "rb") as f:
            info = plistlib.load(f)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return False
    return "UIApplicationSceneManifest" in info or "UIDeviceFamily" in info


def stack_for(framework: str) -> str:
    if framework in WEB_FRAMEWORKS:
        return "web"
    if framework == "qt":
        return "qt"
    if framework == "opaque":
        return "opaque"
    return "native"


def is_browser(bundle_id: str) -> bool:
    return bundle_id in BROWSERS


def node_stack(framework: str, in_webarea: bool) -> str:
    """Rules per node: browser chrome is native, page content is web; Electron is web throughout."""
    if framework in ("electron", "cef", "wkwebview_webapp"):
        return "web"
    if framework in ("webkit_native", "chromium_browser", "gecko"):
        return "web" if in_webarea else "native"
    return stack_for(framework)


def classify_tree(tree: dict, skeleton: dict | None = None, ref_count: int = 1) -> str:
    """Playbook CLASSIFY on an agent-desktop capture, in the codex replay's exact order.
    Coarse classes: opaque | chromium-family | gecko | wkwebview | hybrid | qt | custom | native."""
    nodes: list[tuple[dict, int, tuple]] = []

    def visit(n: dict, d: int, path: tuple) -> None:
        nodes.append((n, d, path))
        for c in n.get("children") or []:
            visit(c, d + 1, path + (n,))

    visit(tree, 0, ())
    n = len(nodes)
    if n == 1 and tree.get("subtree_truncated") and ref_count == 0:        # C0, LAW-LIFE-8
        return "opaque"
    if skeleton is not None:                                               # C1, LAW-LIFE-3
        sk = []
        visit_sk = [skeleton]
        while visit_sk:
            x = visit_sk.pop()
            sk.append(x)
            visit_sk.extend(x.get("children") or [])
        if len(sk) == 7 and len(skeleton.get("children") or []) == 4:
            return "chromium-family"
    webs = [(x, d, p) for x, d, p in nodes if x.get("role") == "webarea"]
    if webs:                                                               # C2, LAW-STR-1
        _, _, path = min(webs, key=lambda z: z[1])
        mids = [q.get("role") for q in path[1:]]
        if "tabpanel" in mids:
            return "gecko"
        if "tablist" in mids:
            return "wkwebview"
        if all(r == "group" for r in mids):
            return "chromium-family"
        return "hybrid"
    ids = [x["native_id"]["value"] for x, _, _ in nodes
           if x.get("native_id") and x["native_id"].get("kind") == "ax_identifier"]
    dotted = sum(1 for v in ids if v.count(".") >= 2 and " " not in v)
    if ids and len(ids) / n >= 0.7 and dotted / len(ids) >= 0.5:           # C3 qt
        return "qt"
    if sum(1 for x, _, _ in nodes if x.get("role") == "row") >= 5:         # C3 custom
        return "custom"
    return "native"
