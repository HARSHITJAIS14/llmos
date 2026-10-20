#!/usr/bin/env python3
"""AX-tree census capture for the atree fidelity ranking.

For each app in the roster: launch hidden if needed (open -gj), capture
list-windows / skeleton / full window tree / surfaces, detect the UI
framework from the bundle, write everything to Ax_analysis/<slug>/, quit
apps we launched, restore the user's frontmost app.

Serial on purpose: AX queries against a launching app are flaky, and the
activation fallback (for husk trees) requires owning the frontmost slot.
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent
AD = "agent-desktop"
ORIGINAL_FRONT = "Antigravity IDE"

# name -> launch name (open -a). Comment = why it's in the roster.
ROSTER = [
    "zoom.us",              # explicit ask: what is Zoom made of?
    "Telegram",             # explicit category-3 candidate
    "Notion",               # Electron anchor (known husk/veil behavior)
    "WhatsApp",             # Catalyst anchor
    "Discord",              # Electron
    "Claude",               # Electron (Anthropic desktop)
    "Postman",              # Electron
    "Canva",                # Electron
    "Visual Studio Code",   # Electron IDE
    "Cursor",               # Electron IDE (VS Code fork)
    "Antigravity IDE",      # Electron IDE (running; the user's editor)
    "OBS",                  # Qt anchor (bounds: None history)
    "VLC",                  # Qt
    "UTM",                  # native SwiftUI
    "Safari",               # browser anchor (running)
    "Brave Browser",        # Chromium browser
    "Google Chrome",        # Chromium browser
    "Firefox",              # Gecko browser — different AX pipeline
    "Finder",               # Apple native anchor (running)
    "Calendar",             # Apple native
    "Notes",                # Apple native
    "Reminders",            # Apple native
    "TextEdit",             # Apple native (simplest possible tree)
    "Music",                # Apple native (JS-backed views)
    "Keynote",              # iWork (custom native canvas)
    "Microsoft Word",       # Office (custom cross-platform native)
    "Gemini",               # com.google.GeminiMacOS (running; framework TBD)
    "YT Music",             # Safari Web App wrapper (running)
]

SKIPPED = {
    "Messages/1Password/etc": "privacy denylist",
    "Xcode, MATLAB, Docker, GarageBand, iMovie": "heavyweight launches, marginal CUA value",
    "AltTab, Rectangle, Raycast, LinearMouse, BetterDisplay, HeyClicky, darker, ...":
        "menubar/background utilities without a main window",
    "BitTorrent*, SmartBrowser, MSB, GtJson, Unstop, HackerRank, Wallper, iwallpaper, MacDroid, EasyCopy, AdBlock, Android File Transfer, Wispr Flow, AClock, Canva? no - included":
        "kiosk/wrapper/utility apps",
    "Microsoft Excel/PowerPoint, Pages/Numbers": "same framework as Word/Keynote (dedup)",
}

WAVE = 6


def sh(args, timeout=30):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"timeout after {timeout}s"


def ad(args, timeout=30):
    code, out, err = sh([AD] + args, timeout)
    try:
        return json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return {"ok": False, "error": {"code": "NON_JSON", "message": (err or out)[:500]}}


def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def running_apps():
    env = ad(["list-apps"])
    return {a["name"]: a for a in env.get("data", {}).get("apps", [])} if env.get("ok") else {}


def best_window(app):
    env = ad(["list-windows", "--app", app], timeout=20)
    wins = env.get("data") if env.get("ok") else None
    if isinstance(wins, dict):
        wins = wins.get("windows", [])
    if not wins:  # Catalyst apps hide from --app filtering (WhatsApp)
        env = ad(["list-windows"], timeout=20)
        allw = env.get("data") or []
        if isinstance(allw, dict):
            allw = allw.get("windows", [])
        wins = [w for w in allw
                if app.lower() in str(w.get("title", "")).lower()
                or app.lower() in str(w.get("app_name", "")).lower()]
    wins = wins or []
    ranked = sorted(wins, key=lambda w: (bool(w.get("is_focused")), bool(w.get("visible")),
                                         str(w.get("title", "")).lower() != app.lower(),
                                         (w.get("bounds") or {}).get("width", 0) > 100), reverse=True)
    return wins, (ranked[0] if ranked else None)


def detect_framework(pid):
    code, out, _ = sh(["ps", "-o", "comm=", "-p", str(pid)])
    exe = out.strip()
    m = re.match(r"(.*?\.app)/", exe)
    bundle = m.group(1) if m else None
    signals = {"exe": exe, "bundle": bundle, "frameworks": [], "hints": []}
    if bundle:
        fw = Path(bundle) / "Contents" / "Frameworks"
        if fw.is_dir():
            names = sorted(p.name for p in fw.iterdir())[:40]
            signals["frameworks"] = names
            joined = " ".join(names)
            if "Electron Framework" in joined:
                signals["hints"].append("electron")
            if "QtCore" in joined or "QtWidgets" in joined:
                signals["hints"].append("qt")
            if "FlutterMacOS" in joined:
                signals["hints"].append("flutter")
            if "Chromium Embedded" in joined or "CEF" in joined:
                signals["hints"].append("cef")
        if (Path(bundle) / "Wrapper").exists() or "Maccatalyst" in exe:
            signals["hints"].append("catalyst")
        info = Path(bundle) / "Contents" / "Info.plist"
        if info.exists():
            code, out, _ = sh(["defaults", "read", str(Path(bundle) / "Contents" / "Info"),
                               "DTSDKName"], timeout=5)
            if "iphoneos" in out:
                signals["hints"].append("catalyst")
    return signals


def capture_one(name, was_running, apps_now):
    d = OUT / slug(name)
    d.mkdir(exist_ok=True)
    meta = {"app": name, "was_running": was_running, "captures": {}, "errors": [],
            "capture_mode": "background"}
    info = apps_now.get(name)
    if not info:
        meta["errors"].append("process never appeared")
        (d / "meta.json").write_text(json.dumps(meta, indent=2))
        return meta
    meta["pid"] = info.get("pid")
    meta["bundle_id"] = info.get("bundle_id")
    meta["framework_signals"] = detect_framework(info.get("pid"))

    wins, best = best_window(name)
    (d / "windows.json").write_text(json.dumps(wins, indent=2))
    meta["captures"]["windows"] = len(wins)
    meta["best_window"] = best

    def snap(label, args):
        env = ad(args, timeout=45)
        (d / f"{label}.json").write_text(json.dumps(env, indent=2))
        ok = bool(env.get("ok"))
        err = (env.get("error") or {}).get("code") if not ok else None
        meta["captures"][label] = {"ok": ok, "bytes": len(json.dumps(env)), "error": err}
        return env

    target = ["--window-id", best["id"]] if best else ["--app", name]
    skel = snap("skeleton", ["snapshot", "--skeleton", "-i", "--compact"] + target)
    full = snap("full", ["snapshot", "-i", "--include-bounds"] + target)
    snap("surfaces", ["list-surfaces", "--app", name])

    # husk / no-AX fallback: briefly activate, recapture, move on
    def is_husk(env):
        if not env.get("ok"):
            return (env.get("error") or {}).get("details", {}).get("kind") == \
                "window_without_accessibility_element" or \
                (env.get("error") or {}).get("code") in ("AMBIGUOUS_TARGET", "APP_UNRESPONSIVE")
        raw = json.dumps(env.get("data", {}))
        return raw.count('"offscreen"') > 0 and raw.count('"name"') < 4

    if is_husk(full) or is_husk(skel):
        meta["capture_mode"] = "activated"
        sh(["open", "-a", name])
        time.sleep(1.6)
        wins, best = best_window(name)
        target = ["--window-id", best["id"]] if best else ["--app", name]
        snap("skeleton", ["snapshot", "--skeleton", "-i", "--compact"] + target)
        full2 = snap("full", ["snapshot", "-i", "--include-bounds"] + target)
        if not full2.get("ok"):
            snap("full", ["snapshot", "-i", "--include-bounds", "--surface", "focused",
                          "--app", name])

    (d / "meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def main():
    t0 = time.time()
    before = running_apps()
    pre_running = {n for n in ROSTER if n in before}
    to_launch = [n for n in ROSTER if n not in before]
    print(f"running: {sorted(pre_running)}")
    print(f"to launch: {to_launch}")

    summary = {}
    for i in range(0, len(ROSTER), WAVE):
        wave = ROSTER[i:i + WAVE]
        launched = [n for n in wave if n not in pre_running]
        for n in launched:
            sh(["open", "-gj", "-a", n], timeout=20)
        if launched:
            time.sleep(7)  # let the wave finish launching
        apps_now = running_apps()
        for n in wave:
            print(f"[{time.time()-t0:5.0f}s] capturing {n} ...", flush=True)
            summary[n] = capture_one(n, n in pre_running, apps_now)
        for n in launched:  # quit what we started, keep the machine clean
            sh(["osascript", "-e", f'tell application "{n}" to quit'], timeout=10)
        time.sleep(1)

    sh(["osascript", "-e", f'tell application "{ORIGINAL_FRONT}" to activate'])
    (OUT / "census_summary.json").write_text(json.dumps(
        {"roster": ROSTER, "skipped": SKIPPED,
         "apps": {k: {kk: v.get(kk) for kk in ("pid", "bundle_id", "capture_mode", "errors", "captures")}
                  for k, v in summary.items()}}, indent=2))
    print(f"done in {time.time()-t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()
