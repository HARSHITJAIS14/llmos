#!/usr/bin/env python3
"""Pass 3: FORCED maximum extraction per app.

Measures the fidelity CEILING: `--max-depth 40` plus recursive drill-down of
every truncated container (children_count>0 with no serialized children),
bounded by a request budget and a wall clock. Writes forced.json per app and
a forced_capture section into meta.json.

Idempotent: skips apps that already have forced.json — safe to re-run if it
times out partway.
"""
import json
import time
from pathlib import Path

import capture as c1  # sh/ad/slug/best_window/running_apps/ORIGINAL_FRONT

OUT = Path(__file__).resolve().parent
DRILL_BUDGET = 40          # max drill requests per app
WALL_SECONDS = 90          # max seconds of drilling per app
WAVE = 6

# retry the four launch-blocked apps by explicit bundle path
BLOCKED = {
    "Postman": "/Applications/Postman.app",
    "Canva": "/Applications/Canva.app",
    "Visual Studio Code": "/Applications/Visual Studio Code.app",
    "Cursor": "/Applications/Cursor.app",
}


def count_nodes(node):
    if not isinstance(node, dict):
        return 0
    return 1 + sum(count_nodes(c) for c in node.get("children") or [])


def count_truncated(node):
    if not isinstance(node, dict):
        return 0
    self_t = 1 if (node.get("children_count", 0) > 0 and not node.get("children")) else 0
    return self_t + sum(count_truncated(c) for c in node.get("children") or [])


def drill(tree, snap_id):
    t0 = time.time()
    stats = {"requests": 0, "ok": 0, "failed": 0, "wall_capped": False}

    def visit(node):
        if not isinstance(node, dict):
            return
        if time.time() - t0 > WALL_SECONDS or stats["requests"] >= DRILL_BUDGET:
            stats["wall_capped"] = True
            return
        if node.get("children_count", 0) > 0 and not node.get("children") and node.get("ref_id"):
            stats["requests"] += 1
            env = c1.ad(["snapshot", "--root", node["ref_id"], "--snapshot", snap_id,
                         "-i", "--include-bounds", "--max-depth", "40"], timeout=45)
            ch = env.get("data", {}).get("tree", {}).get("children") if env.get("ok") else None
            if ch:
                node["children"] = ch
                stats["ok"] += 1
            else:
                stats["failed"] += 1
        for c in node.get("children") or []:
            visit(c)

    visit(tree)
    stats["seconds"] = round(time.time() - t0, 1)
    return stats


def forced_capture(name, d):
    c1.sh(["open", "-a", name])          # fair ceiling: app on screen
    time.sleep(1.5)
    wins, best = c1.best_window(name)
    target = ["--window-id", best["id"]] if best else ["--app", name]
    env = c1.ad(["snapshot", "-i", "--include-bounds", "--max-depth", "40"] + target, timeout=60)
    if not env.get("ok"):
        err = (env.get("error") or {})
        if err.get("details", {}).get("kind") == "window_without_accessibility_element" \
                or err.get("code") == "AMBIGUOUS_TARGET":
            env = c1.ad(["snapshot", "-i", "--include-bounds", "--max-depth", "40",
                         "--surface", "focused", "--app", name], timeout=60)
    result = {"ok": bool(env.get("ok"))}
    if env.get("ok"):
        tree = env.get("data", {}).get("tree", {})
        snap_id = env.get("data", {}).get("snapshot_id")
        result["nodes_before_drill"] = count_nodes(tree)
        result["truncated_before"] = count_truncated(tree)
        if snap_id:
            result["drill"] = drill(tree, snap_id)
        result["nodes_after_drill"] = count_nodes(tree)
        result["truncated_after"] = count_truncated(tree)
        env["data"]["tree"] = tree
    else:
        result["error"] = (env.get("error") or {}).get("code")
    raw = json.dumps(env, indent=1)
    (d / "forced.json").write_text(raw)
    result["bytes"] = len(raw)

    meta_p = d / "meta.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {"app": name}
    meta["forced_capture"] = result
    meta_p.write_text(json.dumps(meta, indent=2))
    return result


def main():
    # roster = every captured dir + blocked retries
    jobs = []
    for d in sorted(OUT.iterdir()):
        if d.is_dir() and (d / "meta.json").exists() and not (d / "forced.json").exists():
            meta = json.loads((d / "meta.json").read_text())
            if meta.get("errors") and "never appeared" in " ".join(meta["errors"]):
                continue
            jobs.append((meta.get("app", d.name), d))
    for name, path in BLOCKED.items():
        d = OUT / c1.slug(name)
        if not (d / "forced.json").exists():
            jobs.append((name, None))  # None dir -> needs full first capture too

    before = c1.running_apps()
    launched = []
    for i in range(0, len(jobs), WAVE):
        wave = jobs[i:i + WAVE]
        for name, _ in wave:
            if name not in before and not any(name.lower() in b.lower() for b in before):
                tgt = BLOCKED.get(name)
                c1.sh(["open", "-gj", tgt] if tgt else ["open", "-gj", "-a", name], timeout=20)
                launched.append(name)
        time.sleep(8)
        apps_now = c1.running_apps()
        for name, d in wave:
            # fuzzy-resolve the live process name
            live = name if name in apps_now else next(
                (n for n in apps_now if name.lower() in n.lower() or n.lower() in name.lower()), None)
            if not live:
                print(f"SKIP {name}: not running", flush=True)
                continue
            if d is None:  # blocked app finally launched: do the default captures first
                apps_now2 = c1.running_apps()
                c1.capture_one(live, False, apps_now2)
                src, dst = OUT / c1.slug(live), OUT / c1.slug(name)
                if src != dst and src.exists() and not dst.exists():
                    src.rename(dst)
                d = OUT / c1.slug(name)
            t0 = time.time()
            r = forced_capture(live, d)
            dr = r.get("drill", {})
            print(f"[forced] {name:<22} ok={r['ok']} {r.get('nodes_before_drill','-'):>5} -> "
                  f"{r.get('nodes_after_drill','-'):>5} nodes, drills {dr.get('ok',0)}/{dr.get('requests',0)}, "
                  f"{r['bytes']//1024}KB, {time.time()-t0:.0f}s", flush=True)
        for name in [n for n, _ in wave if n in launched]:
            c1.sh(["osascript", "-e", f'tell application "{name}" to quit'], timeout=10)

    c1.sh(["osascript", "-e", f'tell application "{c1.ORIGINAL_FRONT}" to activate'])
    print("forced pass done")


if __name__ == "__main__":
    main()
