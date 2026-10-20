#!/usr/bin/env python3
"""Pass 3b: fix-ups for the forced-extraction census.
- correct drill detector: subtree_truncated OR children_count gap (0.8.1 vs 0.4.0)
- correct process resolution: exact name, else foreground-only substring
- RefMap-overflow fallback: retry without -i (loses refs -> drill impossible, noted)
- launch with per-app polling for slow starters
"""
import json
import time
import unicodedata
from pathlib import Path

import capture as c1

OUT = Path(__file__).resolve().parent
DRILL_BUDGET, WALL = 60, 120

REDRILL = {"Finder": "finder", "Keynote": "keynote", "Reminders": "reminders", "Telegram": "telegram"}
RETRY_FAILED = {"Antigravity IDE": "antigravity_ide", "Gemini": "gemini", "UTM": "utm"}
LAUNCH = {"OBS Studio": ("obs", None), "WhatsApp": ("whatsapp", None),
          "Postman": ("postman", "/Applications/Postman.app"),
          "Canva": ("canva", "/Applications/Canva.app"),
          "Visual Studio Code": ("visual_studio_code", "/Applications/Visual Studio Code.app"),
          "Cursor": ("cursor", "/Applications/Cursor.app")}


def clean(s):
    return "".join(ch for ch in s if unicodedata.category(ch) != "Cf").strip().lower()


def resolve(name):
    apps = c1.running_apps()
    for n in apps:
        if clean(n) == clean(name):
            return n
    for n, a in apps.items():
        if a.get("presentation") == "foreground" and (clean(name) in clean(n) or clean(n) in clean(name)):
            return n
    return None


def truncated(node):
    return bool(node.get("subtree_truncated")) or \
        node.get("children_count", 0) > len(node.get("children") or [])


def count_nodes(n):
    return 1 + sum(count_nodes(c) for c in (n.get("children") or [])) if isinstance(n, dict) else 0


def drill(tree, snap_id):
    t0, stats = time.time(), {"requests": 0, "ok": 0, "failed": 0}
    def visit(node):
        if not isinstance(node, dict) or time.time() - t0 > WALL or stats["requests"] >= DRILL_BUDGET:
            return
        if truncated(node) and node.get("ref_id"):
            stats["requests"] += 1
            env = c1.ad(["snapshot", "--root", node["ref_id"], "--snapshot", snap_id,
                         "-i", "--include-bounds", "--max-depth", "40"], timeout=45)
            got = env.get("data", {}).get("tree", {}) if env.get("ok") else {}
            if got.get("children"):
                node["children"] = got["children"]
                node.pop("subtree_truncated", None)
                stats["ok"] += 1
            else:
                stats["failed"] += 1
                node["drill_result"] = (env.get("error") or {}).get("code") or "empty"
        for c in node.get("children") or []:
            visit(c)
    visit(tree)
    stats["seconds"] = round(time.time() - t0, 1)
    return stats


def forced(name, dirname):
    d = OUT / dirname
    d.mkdir(exist_ok=True)
    live = resolve(name)
    if not live:
        print(f"SKIP {name}: not running")
        return
    c1.sh(["open", "-a", live])
    time.sleep(1.5)
    wins, best = c1.best_window(live)
    target = ["--window-id", best["id"]] if best else ["--app", live]
    args = ["snapshot", "-i", "--include-bounds", "--max-depth", "40"] + target
    env = c1.ad(args, timeout=60)
    note = ""
    if not env.get("ok"):
        code = (env.get("error") or {}).get("code")
        if code == "INTERNAL":  # RefMap overflow on giant trees
            env = c1.ad(["snapshot", "--include-bounds", "--max-depth", "40"] + target, timeout=60)
            note = "captured without -i (RefMap>1MB): refs unavailable, drilling impossible"
        elif code in ("AMBIGUOUS_TARGET",) or (env.get("error") or {}).get(
                "details", {}).get("kind") == "window_without_accessibility_element":
            env = c1.ad(["snapshot", "-i", "--include-bounds", "--max-depth", "40",
                         "--surface", "focused", "--app", live], timeout=60)
    result = {"ok": bool(env.get("ok")), "note": note}
    if env.get("ok"):
        tree = env["data"].get("tree", {})
        snap_id = env["data"].get("snapshot_id")
        result["nodes_before_drill"] = count_nodes(tree)
        if snap_id and "without -i" not in note:
            result["drill"] = drill(tree, snap_id)
        result["nodes_after_drill"] = count_nodes(tree)
        env["data"]["tree"] = tree
    else:
        result["error"] = (env.get("error") or {}).get("code")
    raw = json.dumps(env, indent=1)
    (d / "forced.json").write_text(raw)
    result["bytes"] = len(raw)
    meta_p = d / "meta.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {"app": live}
    meta["forced_capture"] = result
    meta_p.write_text(json.dumps(meta, indent=2))
    dr = result.get("drill", {})
    print(f"[forced2] {name:<20} ok={result['ok']} nodes {result.get('nodes_before_drill','-')} -> "
          f"{result.get('nodes_after_drill','-')}, drills {dr.get('ok',0)}/{dr.get('requests',0)} "
          f"(fail {dr.get('failed',0)}), {result['bytes']//1024}KB {note}")


def main():
    launched = []
    # slow launchers: start all, then poll each
    for name, (dirname, path) in LAUNCH.items():
        if not resolve(name):
            c1.sh(["open", "-gj", path] if path else ["open", "-gj", "-a", name], timeout=20)
            launched.append(name)
    for name, dirname in {**REDRILL, **RETRY_FAILED}.items():
        if not resolve(name):
            c1.sh(["open", "-gj", "-a", name], timeout=20)
            launched.append(name)

    for name, dirname in {**REDRILL, **RETRY_FAILED}.items():
        deadline = time.time() + 30
        while not resolve(name) and time.time() < deadline:
            time.sleep(2)
        forced(name, dirname)
    for name, (dirname, path) in LAUNCH.items():
        deadline = time.time() + 45
        while not resolve(name) and time.time() < deadline:
            time.sleep(3)
        live = resolve(name)
        if live and not (OUT / dirname / "full.json").exists():
            c1.capture_one(live, False, c1.running_apps())  # default captures too
            src = OUT / c1.slug(live)
            if src != OUT / dirname and src.exists():
                src.rename(OUT / dirname)
        forced(name, dirname)

    for name in launched:
        live = resolve(name)
        if live:
            c1.sh(["osascript", "-e", f'tell application "{live}" to quit'], timeout=10)
    c1.sh(["osascript", "-e", f'tell application "{c1.ORIGINAL_FRONT}" to activate'])
    print("pass 3b done")


if __name__ == "__main__":
    main()
