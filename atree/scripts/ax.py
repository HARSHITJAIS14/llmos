#!/usr/bin/env python3
"""ax — the model-facing entrypoint for atree. One fat command per loop step,
so the right thing is the easy thing:

  ax recall  "<task>" [App]        what do we already know? (L1/L2/L3/miss)
  ax observe <App>                 ghost-aware skeleton capture -> compact digest + diff
  ax find    <App> <text> [role]   locate click targets: name, ref, bounds, center
  ax open    <App>                 launch/activate an app and verify it is frontmost.
                                   NEVER open apps via Spotlight, Dock, or UI navigation.
  ax type    <App> <text> ['<pc-json>']
                                   enter text THE fast way: clipboard-set + Cmd+V
                                   (atomic paste; real input events so Electron/React
                                   registers it; the user's clipboard is restored).
                                   NEVER type character by character.
  ax do      '<pc-json>' -- <agent-desktop action args...>
                                   declare + act + verify, atomically. exit 2 on fail.
  ax guide   [topic|App]           the knowledge tier on demand: archetype quirks and
                                   working strategies (e.g. ax guide notion). Call this
                                   BEFORE automating an unfamiliar app.

Raw trees never reach stdout; state lives in ~/.atree/state regardless of cwd.
This replaces the fragile "redirect every snapshot to a magic path" convention
— perception compression no longer depends on hooks firing.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(PLUGIN_ROOT))

from core import axdiff, registry, snapshot  # noqa: E402
from core.postconditions import Postcondition, evaluate_live  # noqa: E402

STATE_DIR = Path.home() / ".atree" / "state"
OUTCOMES = STATE_DIR / "outcomes.jsonl"


def _slug(app: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", app.lower()).strip("-")


def _last(app: str) -> Path:
    return STATE_DIR / f"last_{_slug(app)}.json"      # diffs are per-app


def _sidecar(app: str) -> Path:
    return STATE_DIR / f"sidecar_{_slug(app)}.json"

INTERACTIVE = {"button", "textfield", "textarea", "searchfield", "combobox", "checkbox",
               "menuitem", "tab", "link", "slider", "popupbutton", "cell", "radiobutton"}

PHYSICAL = re.compile(r"^(mouse-click|mouse-move|double-click|triple-click|drag|hover|press|type)$")


def _die(msg: str, code: int = 1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def _center(b: dict | None) -> str:
    if not b:
        return "-"
    return f"({int(b['x'] + b.get('width', 0) / 2)},{int(b['y'] + b.get('height', 0) / 2)})"


def cmd_recall(args: list[str]):
    from core import recall
    task = args[0] if args else _die("usage: ax recall \"<task>\" [App]")
    app = args[1] if len(args) > 1 else None
    print(json.dumps(recall.recall(task, app), indent=2))


def cmd_observe(args: list[str]):
    app = args[0] if args else _die("usage: ax observe <App> [--surface focused]")
    surface = "focused" if "--surface" in args or "focused" in args[1:] else None
    try:
        env = snapshot.capture(app=app, surface=surface)  # ghost/Space-aware
    except RuntimeError as e:
        _die(f"observe failed: {e}\nTry: ax observe \"{app}\" --surface focused "
             f"(after activating the app), or `agent-desktop list-windows --app \"{app}\"`.")

    tree = env.get("data", {}).get("tree", env)
    content, sidecar = axdiff.flatten(tree)

    # The Electron veil (electron.md): a truncated webarea yields a digest with
    # nothing to click. Drill down (bounded) before reporting emptiness.
    n_interactive = sum(1 for a in content.values() if a.get("role") in INTERACTIVE and a.get("name"))
    snap_id = env.get("data", {}).get("snapshot_id")
    if n_interactive < 5 and snap_id:
        tree = snapshot.expand_truncated(tree, snap_id, max_requests=10)
        content, sidecar = axdiff.flatten(tree)
        n_interactive = sum(1 for a in content.values() if a.get("role") in INTERACTIVE and a.get("name"))

    # Husk detection: a window on a non-active Space exposes a stub tree where
    # everything is offscreen and nothing is named. Observing it is useless.
    if n_interactive == 0 and len(content) < 40:
        raw_states = json.dumps(env.get("data", {}))
        if '"offscreen"' in raw_states:
            _die(f"{app}'s window is on a non-active Space — macOS exposes only a stub tree "
                 f"({len(content)} nodes, all offscreen). Bring it on screen first:\n"
                 f"  osascript -e 'tell application \"{app}\" to reopen' -e 'tell application \"{app}\" to activate'\n"
                 f"then re-run: ax observe \"{app}\"  (note: this switches the user's screen)")

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    last, side = _last(app), _sidecar(app)
    prev = json.loads(last.read_text()) if last.exists() else None
    last.write_text(json.dumps(tree))
    side.write_text(json.dumps(sidecar))

    # deposit into the registry (selectors-not-content handled inside)
    if not registry.denied(app):
        con = registry.connect()
        app_id = registry.get_or_create_app(con, app)
        if app_id is not None:
            n = 0
            content_hint = re.compile(r"/(webarea|list|table|outline|row|cell)\b", re.I)
            for path, attrs in content.items():
                if attrs.get("role") in INTERACTIVE and attrs.get("name") and n < 200:
                    registry.upsert_element(con, app_id, path, attrs["role"], str(attrs["name"]),
                                            is_content=bool(content_hint.search(path)))
                    n += 1

    if prev is not None:
        d = axdiff.diff(prev, tree)
        if not d.is_empty and d.changed <= 120:
            print(f"[diff vs previous capture: +{d.added}/-{d.removed} lines, ~{d.tokens} tok]")
            print(d.text)
            return
        if d.is_empty:
            print("[no change since previous capture]")
            return

    # first look (or huge transition): print the interactive digest, not the tree
    rows = [(p, a) for p, a in sorted(content.items()) if a.get("role") in INTERACTIVE and a.get("name")]
    print(f"[{app}: {len(content)} nodes, {len(rows)} named interactive elements. "
          f"Click via `ax find` or the centers below — never via screenshot.]")
    for path, attrs in rows[:60]:
        ref = (sidecar.get(path) or {}).get("ref_id") or "-"
        print(f"  {attrs['role']:<12} {str(attrs['name'])[:48]:<50} ref={ref:<14} center={_center((sidecar.get(path) or {}).get('bounds'))}")
    if len(rows) > 60:
        print(f"  ... {len(rows) - 60} more — narrow with `ax find {app} <text>`")


def cmd_find(args: list[str]):
    if len(args) < 2:
        _die("usage: ax find <App> <text> [role]")
    app, text = args[0], args[1]
    role = args[2] if len(args) > 2 else None
    env = snapshot.find(app=app, name=text, role=role)
    hits = env.get("data", {}).get("matches", env.get("data", {}).get("elements", [])) if env.get("ok") else []
    if not hits:  # fall back to a fresh capture + flatten search (find can miss webareas)
        try:
            cap = snapshot.capture(app=app)
            content, sidecar = axdiff.flatten(cap.get("data", {}).get("tree", cap))
            for path, attrs in content.items():
                if text.lower() in str(attrs.get("name", "")).lower() and (not role or attrs.get("role") == role):
                    sc = sidecar.get(path) or {}
                    hits.append({"role": attrs.get("role"), "name": attrs.get("name"),
                                 "ref_id": sc.get("ref_id"), "bounds": sc.get("bounds"), "path": path})
        except RuntimeError as e:
            _die(f"find failed: {e}")
    if not hits:
        _die(f"no element matching {text!r} in {app}. Widen: ax observe \"{app}\"", 1)
    print(f"[{len(hits)} match(es)] click semantically via `ax do '<pc>' -- click <ref>` "
          f"or physically at the center (activate the app first for physical clicks):")
    for h in hits[:15]:
        print(f"  {h.get('role', '?'):<12} {str(h.get('name', ''))[:48]:<50} "
              f"ref={h.get('ref_id') or '-':<16} center={_center(h.get('bounds'))}")


# topic -> reference file. App names map to their archetype so an agent can
# ask about "Notion" without knowing our taxonomy.
GUIDE_MAP = {
    "index": "archetypes.md", "archetypes": "archetypes.md",
    "electron": "electron.md", "notion": "electron.md", "vscode": "electron.md",
    "slack": "electron.md", "discord": "electron.md", "spotify": "electron.md",
    "catalyst": "catalyst.md", "native": "catalyst.md", "finder": "catalyst.md",
    "safari": "catalyst.md", "calendar": "catalyst.md", "whatsapp": "catalyst.md",
    "mail": "catalyst.md", "notes": "catalyst.md",
    "qt": "qt-opaque.md", "qt-opaque": "qt-opaque.md", "obs": "qt-opaque.md",
    "browser": "browser.md", "web": "browser.md", "youtube": "browser.md",
    "chrome": "browser.md", "brave": "browser.md",
    "dialogs": "dialogs.md", "save": "dialogs.md", "open": "dialogs.md",
    "picker": "dialogs.md", "settings": "dialogs.md",
    "rich-text": "rich-text.md", "formatting": "rich-text.md", "paste": "rich-text.md",
    "cli": "agent-desktop-cli.md", "agent-desktop": "agent-desktop-cli.md",
    "flags": "agent-desktop-cli.md",
}


def cmd_guide(args: list[str]):
    """Serve the confirmed knowledge tier on demand — the progressive-
    disclosure lookup as a command, so MCP hosts (which never see skill
    files) get the same archetype knowledge Claude Code gets."""
    refs = PLUGIN_ROOT / "skills" / "atree" / "references"
    topic = (args[0] if args else "index").strip().lower()
    fname = GUIDE_MAP.get(topic)
    if fname is None:  # try app-name recall: registry knows its archetype
        try:
            con = registry.connect()
            row = con.execute("SELECT archetype FROM apps WHERE lower(name)=?", (topic,)).fetchone()
            if row and row["archetype"]:
                fname = GUIDE_MAP.get(row["archetype"])
        except Exception:
            pass
    if fname is None:
        print((refs / "archetypes.md").read_text())
        print(f"\n[no guide matched {topic!r} — the index above tells you which "
              f"archetype to ask for. Topics: {', '.join(sorted(set(GUIDE_MAP)))}]")
        return
    print((refs / fname).read_text())
    if fname != "archetypes.md":
        print("\n[Rules that always apply: text entry via `ax type` (clipboard paste, "
              "never per-character); declare a postcondition for every action (`ax do`); "
              "never screenshot to find elements; open apps via `ax open`, never Spotlight/Dock; "
              "multiple candidate targets -> ask the user; "
              "no automation of Messages/password managers/banking without an explicit instruction.]")


def cmd_open(args: list[str]):
    """App launching as a verb (original learnings §4): osascript reopen +
    activate. Launches if not running, recreates a closed main window,
    brings it frontmost — atomically. NEVER Spotlight, never Dock, never UI
    navigation to open an app."""
    if not args:
        _die("usage: ax open <App>")
    app = args[0]
    r = subprocess.run(["osascript", "-e", f'tell application "{app}" to reopen',
                        "-e", f'tell application "{app}" to activate'],
                       capture_output=True, text=True)
    if r.returncode != 0:  # name mismatch etc. — try LaunchServices
        r2 = subprocess.run(["open", "-a", app], capture_output=True, text=True)
        if r2.returncode != 0:
            _die(f"could not open {app!r}: {r.stderr.strip() or r2.stderr.strip()}", 2)

    # verify: a window of the app becomes focused or visible (predicate poll,
    # with the Catalyst fallback — WhatsApp etc. hide from --app filtering)
    deadline = time.monotonic() + 6.0
    win = None
    while time.monotonic() < deadline and win is None:
        wins = snapshot.list_windows(app) or [
            w for w in snapshot.list_windows() if app.lower() in str(w.get("title", "")).lower()
            or app.lower() in str(w.get("app_name", "")).lower()]
        win = next((w for w in wins if w.get("is_focused")), None) \
            or next((w for w in wins if w.get("visible")), None)
        if win is None:
            time.sleep(0.4)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with OUTCOMES.open("a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "action": f"open {app}", "app": app,
                            "postcondition": {"kind": "window_visible", "description": "app frontmost"},
                            "verdict": "pass" if win else "fail",
                            "detail": (win or {}).get("title", "no window")}) + "\n")
    if win:
        print(f"VERIFIED: {app} is frontmost — window {win.get('id')} "
              f"{win.get('title', '')!r} (focused={win.get('is_focused')}, visible={win.get('visible')})")
        return
    _die(f"{app} was activated but no window became visible within 6s. "
         f"Check the app name (`agent-desktop list-apps --app {app}`) or whether "
         "it opens on another Space; then `ax observe` once it is on screen.", 2)


def cmd_type(args: list[str]):
    """The clipboard macro from the original learnings §3, as a verb:
    clipboard-set + activate + Cmd+V. Atomic, fast (seconds vs minutes),
    survives Electron/React (real input events), preserves formatting —
    and restores whatever the user had on their clipboard."""
    if len(args) < 2:
        _die("usage: ax type <App> <text> ['<postcondition-json>']\n"
             "Pastes via clipboard — never type character by character.")
    app, text = args[0], args[1]
    pc = None
    if len(args) > 2:
        try:
            pc = Postcondition.from_json(args[2])
        except Exception as e:
            _die(f"bad postcondition JSON: {e}")

    # save the user's clipboard (text only; skip restore for images/files)
    saved = subprocess.run([snapshot.agent_bin(), "clipboard-get"],
                           capture_output=True, text=True)
    old_clip = None
    try:
        env = json.loads(saved.stdout)
        if env.get("ok"):
            old_clip = env.get("data", {}).get("text")
    except (json.JSONDecodeError, ValueError):
        pass

    snapshot.run(["clipboard-set", text])
    subprocess.run(["osascript", "-e", f'tell application "{app}" to reopen',
                    "-e", f'tell application "{app}" to activate'], capture_output=True)
    subprocess.run([snapshot.agent_bin(), "wait", "400"], capture_output=True)
    res = snapshot.run(["press", "cmd+v"])
    subprocess.run([snapshot.agent_bin(), "wait", "500"], capture_output=True)
    if old_clip is not None:
        snapshot.run(["clipboard-set", old_clip])

    if not res.get("ok"):
        _die(f"paste keystroke failed: {json.dumps(res.get('error', res))[:300]}", 2)

    # verify: declared postcondition, else wait for the text to render
    if pc is not None:
        verdict = evaluate_live(pc)
        ok, detail = verdict.ok, verdict.detail
    else:
        snippet = text.splitlines()[0][:24]
        w = snapshot.run(["wait", "--text", snippet, "--app", app, "--timeout", "4000"],
                         timeout=10)
        ok, detail = bool(w.get("ok")), (f"text {snippet!r} rendered in {app}" if w.get("ok")
                                         else f"text {snippet!r} did not render within 4s")

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with OUTCOMES.open("a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "action": f"type via clipboard ({len(text)} chars)", "app": app,
                            "postcondition": {"kind": pc.kind if pc else "wait_text",
                                              "description": (pc.description if pc else "pasted text renders")},
                            "verdict": "pass" if ok else "fail", "detail": detail}) + "\n")
    if ok:
        print(f"VERIFIED: pasted {len(text)} chars into {app} — {detail} (clipboard restored)")
        return
    _die(f"PASTE UNVERIFIED: {detail}\n"
         "The paste keystroke was sent but the text is not confirmed on screen. "
         f"Check focus was in the right field: ax observe \"{app}\". Do not re-paste blindly.", 2)


def cmd_do(args: list[str]):
    if "--" not in args:
        _die("usage: ax do '<postcondition-json>' -- <agent-desktop action args...>\n"
             "e.g. ax do '{\"kind\":\"title_matches\",\"expect\":{\"pattern\":\"cursor for che\"},\"app\":\"Notion\"}' "
             "-- mouse-click --xy 295,647")
    split = args.index("--")
    pc_raw, action = args[:split], args[split + 1:]
    if not pc_raw or not action:
        _die("ax do: need both a postcondition and an action")
    try:
        pc = Postcondition.from_json(pc_raw[0])
    except Exception as e:
        _die(f"bad postcondition JSON: {e}\nkinds: node_exists node_absent value_equals value_contains title_matches\n"
             "expect for title_matches: {\"pattern\": \"...\"}")

    # catalyst.md focus rule: physical input needs the app active; semantic must NOT activate
    if pc.app and PHYSICAL.match(action[0]):
        subprocess.run(["osascript", "-e", f'tell application "{pc.app}" to reopen',
                        "-e", f'tell application "{pc.app}" to activate'], capture_output=True)
        subprocess.run([snapshot.agent_bin(), "wait", "500"], capture_output=True)

    # Stealth-click rule (original ATree_tool learnings §4): physical clicks go
    # through the CoreGraphics binary that saves the user's pointer, clicks,
    # and returns the pointer within milliseconds — never hijack their hand.
    stealth = Path(__file__).with_name("stealth_click")
    if action[0] == "mouse-click" and "--xy" in action and stealth.exists():
        xy = action[action.index("--xy") + 1]
        r = subprocess.run([str(stealth)] + xy.split(","), capture_output=True, text=True)
        res = {"ok": r.returncode == 0,
               "data": {"clicked": True, "stealth": True, "xy": xy}} if r.returncode == 0 \
              else {"ok": False, "error": {"message": r.stdout.strip() or r.stderr.strip()}}
    else:
        res = snapshot.run(action)
    if not res.get("ok"):
        _die(f"action failed before verification: {json.dumps(res.get('error', res))[:400]}", 2)

    verdict = evaluate_live(pc)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with OUTCOMES.open("a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "action": " ".join(action)[:300], "app": pc.app,
                            "postcondition": {"kind": pc.kind, "expect": pc.expect,
                                              "description": pc.description},
                            "verdict": "pass" if verdict.ok else "fail",
                            "detail": verdict.detail}) + "\n")
    if verdict.ok:
        print(f"VERIFIED: {pc.description or pc.kind} — {verdict.detail}"
              + (f" (at {verdict.matched_path})" if verdict.matched_path else ""))
        return
    _die(f"POSTCONDITION FAILED: {pc.description or pc.kind}\n"
         f"  expected: {json.dumps(pc.expect)}\n  observed: {verdict.detail}\n"
         "Do NOT retry blindly. Diagnose: ax observe (what changed?), then the free vision "
         "rungs (python3 -m core.vision), then ONE cropped screenshot read.", 2)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        return
    cmd, rest = sys.argv[1], sys.argv[2:]
    dispatch = {"recall": cmd_recall, "observe": cmd_observe, "find": cmd_find,
                "type": cmd_type, "do": cmd_do, "guide": cmd_guide, "open": cmd_open}
    if cmd not in dispatch:
        _die(f"unknown subcommand {cmd!r}\n\n{__doc__.strip()}")
    dispatch[cmd](rest)


if __name__ == "__main__":
    main()
