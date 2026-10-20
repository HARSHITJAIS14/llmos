#!/usr/bin/env python3
"""Pass 2: re-capture apps that launched too slowly or were shot mid-splash.
Differences from pass 1: fuzzy process-name matching, poll up to 30s for the
process, 6s settle after launch, activation before capture, capture, quit."""
import json
import subprocess
import time
from pathlib import Path

import capture as c1  # reuse sh/ad/slug/best_window/detect_framework/capture_one

OUT = Path(__file__).resolve().parent

RETRY = ["WhatsApp", "Postman", "Canva", "Visual Studio Code", "Cursor", "OBS",
         "Discord", "Microsoft Word", "Keynote", "Telegram", "Notion", "Claude"]


def fuzzy_running(name):
    apps = c1.running_apps()
    if name in apps:
        return name, apps
    low = name.lower()
    for n in apps:
        if low in n.lower() or n.lower() in low:
            return n, apps
    return None, apps


def main():
    before = c1.running_apps()
    pre = {n for n in RETRY if fuzzy_running(n)[0]}
    launched = []
    for name in RETRY:
        match, _ = fuzzy_running(name)
        if not match:
            c1.sh(["open", "-ga", name], timeout=20)
            launched.append(name)

    for name in RETRY:
        match = None
        deadline = time.time() + 30
        while time.time() < deadline and not match:
            match, apps = fuzzy_running(name)
            if not match:
                time.sleep(2)
        if not match:
            print(f"SKIP {name}: never appeared")
            continue
        print(f"capturing {name} (process {match!r}) ...", flush=True)
        time.sleep(6 if name in launched else 1)
        c1.sh(["open", "-a", match])          # fair capture: on-screen
        time.sleep(2.0)
        apps = c1.running_apps()
        meta = c1.capture_one(match, name not in launched, apps)
        # keep folder named by roster name for consistency
        if c1.slug(match) != c1.slug(name):
            src, dst = OUT / c1.slug(match), OUT / c1.slug(name)
            if src.exists():
                if dst.exists():
                    for f in src.iterdir():
                        f.rename(dst / f.name)
                    src.rmdir()
                else:
                    src.rename(dst)

    for name in launched:
        match, _ = fuzzy_running(name)
        if match:
            c1.sh(["osascript", "-e", f'tell application "{match}" to quit'], timeout=10)
    c1.sh(["osascript", "-e", f'tell application "{c1.ORIGINAL_FRONT}" to activate'])
    print("pass 2 done")


if __name__ == "__main__":
    main()
