"""Automated 1,000-Screen Real Capture Script across macOS.

Safely captures real screenshots across installed native macOS applications:
- Both full desktop screens and window-isolated screens.
- Rich variety: System Settings, Finder, Safari, Chrome, Calendar, Activity Monitor,
  Calculator, Clock, Stocks, Maps, Font Book, App Store, Podcasts, Music, TV, Books,
  TextEdit, Preview, Numbers, Terminal, VS Code, and Desktop states.
- STRICT SAFETY: Zero interaction with communication/email apps (Mail, Messages, Telegram, WhatsApp, etc.).
- No destructive actions, no text sent to emails/chats, no file deletion.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Dict, List, Optional

from PIL import Image
import Quartz

OUTPUT_DIR = Path("/Users/harshit/Desktop/YC/screen_understanding/dataset/captures_1000")
SCREENS_DIR = OUTPUT_DIR / "screens"
MANIFEST_PATH = OUTPUT_DIR / "manifest.jsonl"
SUMMARY_PATH = OUTPUT_DIR / "summary.json"

IGNORE_APPS = {
    "Wispr Flow", "AltTab", "Rectangle", "LinearMouse", "Window Server",
    "Control Centre", "Notification Center", "Spotlight", "loginwindow", "Dock"
}

BLACKLISTED_APPS = {
    "Mail", "Messages", "Telegram", "WhatsApp", "FaceTime", "Phone",
    "Passwords", "BitTorrent", "BitTorrent Web", "Keychain Access", "Wallet",
    "Cardboard", "Unstop SmartHire"
}


def run_osascript(script: str) -> str:
    try:
        res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5)
        return res.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"


def get_window_for_app(app_name: str) -> Optional[Dict[str, Any]]:
    windows = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID
    )
    for w in windows:
        owner = w.get("kCGWindowOwnerName", "")
        wid = w.get("kCGWindowNumber", 0)
        bounds = w.get("kCGWindowBounds", {})
        w_w = bounds.get("Width", 0)
        w_h = bounds.get("Height", 0)
        title = w.get("kCGWindowName", "")
        if app_name.lower() in owner.lower() and w_w > 250 and w_h > 150:
            return {
                "wid": wid,
                "app": owner,
                "title": title or app_name,
                "width": int(w_w),
                "height": int(w_h)
            }
    return None


def get_frontmost_window() -> Optional[Dict[str, Any]]:
    windows = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID
    )
    for w in windows:
        owner = w.get("kCGWindowOwnerName", "")
        if owner in IGNORE_APPS or owner in BLACKLISTED_APPS:
            continue
        wid = w.get("kCGWindowNumber", 0)
        bounds = w.get("kCGWindowBounds", {})
        w_w = bounds.get("Width", 0)
        w_h = bounds.get("Height", 0)
        title = w.get("kCGWindowName", "")
        if w_w > 300 and w_h > 200:
            return {
                "wid": wid,
                "app": owner,
                "title": title or owner,
                "width": int(w_w),
                "height": int(w_h)
            }
    return None


class ScreenCaptureManager:
    def __init__(self, target_count: int = 1000):
        self.target_count = target_count
        self.count = 0
        self.manifest_file = None
        SCREENS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Check existing captures if resuming
        if MANIFEST_PATH.exists():
            with open(MANIFEST_PATH, "r") as f:
                self.count = sum(1 for line in f if line.strip())
            print(f"Resuming capture from existing {self.count} screens...")
        
        self.manifest_file = open(MANIFEST_PATH, "a")

    def capture_state(self, app_name: str, state_desc: str, stratum: str, capture_both: bool = True):
        if self.count >= self.target_count:
            return

        w_info = get_window_for_app(app_name) or get_frontmost_window()
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # 1. Capture window if available
        if w_info:
            wid = w_info["wid"]
            self.count += 1
            screen_id = f"screen_{self.count:04d}"
            filename = f"{screen_id}.png"
            filepath = SCREENS_DIR / filename
            
            subprocess.run(["screencapture", "-x", "-o", f"-l{wid}", str(filepath)], check=False)
            
            if filepath.exists() and filepath.stat().st_size > 0:
                with open(filepath, "rb") as f:
                    file_bytes = f.read()
                    sha256 = hashlib.sha256(file_bytes).hexdigest()
                try:
                    with Image.open(filepath) as img:
                        dims = [img.width, img.height]
                except Exception:
                    dims = [w_info["width"] * 2, w_info["height"] * 2]

                record = {
                    "id": screen_id,
                    "filename": filename,
                    "capture_type": "window",
                    "app_name": w_info["app"],
                    "window_title": w_info.get("title", ""),
                    "state_description": state_desc,
                    "stratum": stratum,
                    "dimensions": dims,
                    "scale_factor": 2.0,
                    "sha256": sha256,
                    "timestamp": timestamp,
                }
                self.manifest_file.write(json.dumps(record) + "\n")
                self.manifest_file.flush()

                if self.count % 25 == 0:
                    print(f"[{self.count}/{self.target_count}] Captured {screen_id}: {w_info['app']} ({state_desc})")

        # 2. Capture full desktop
        if capture_both and self.count < self.target_count:
            self.count += 1
            screen_id = f"screen_{self.count:04d}"
            filename = f"{screen_id}.png"
            filepath = SCREENS_DIR / filename
            
            subprocess.run(["screencapture", "-x", str(filepath)], check=False)
            
            if filepath.exists() and filepath.stat().st_size > 0:
                with open(filepath, "rb") as f:
                    file_bytes = f.read()
                    sha256 = hashlib.sha256(file_bytes).hexdigest()
                try:
                    with Image.open(filepath) as img:
                        dims = [img.width, img.height]
                except Exception:
                    dims = [2880, 1800]

                record = {
                    "id": screen_id,
                    "filename": filename,
                    "capture_type": "fullscreen",
                    "app_name": w_info["app"] if w_info else "Desktop",
                    "window_title": "Full Desktop",
                    "state_description": f"Full screen view with {state_desc}",
                    "stratum": stratum,
                    "dimensions": dims,
                    "scale_factor": 2.0,
                    "sha256": sha256,
                    "timestamp": timestamp,
                }
                self.manifest_file.write(json.dumps(record) + "\n")
                self.manifest_file.flush()

                if self.count % 25 == 0:
                    print(f"[{self.count}/{self.target_count}] Captured {screen_id}: Fullscreen ({state_desc})")

    def close(self):
        if self.manifest_file:
            self.manifest_file.close()


def run_campaign():
    manager = ScreenCaptureManager(target_count=1000)
    print(f"Starting 1,000-screen capture campaign at {datetime.datetime.now()}...")

    # =========================================================================
    # STRATUM 4: System Settings (25 panels x 2 captures = ~50 screens)
    # =========================================================================
    print("\n--- Capturing Stratum 4: System Settings Panels ---")
    settings_panels = [
        ("Appearance", "x-apple.systempreferences:com.apple.Appearance-Settings.extension"),
        ("Displays", "x-apple.systempreferences:com.apple.Displays-Settings.extension"),
        ("Sound", "x-apple.systempreferences:com.apple.Sound-Settings.extension"),
        ("Wallpaper", "x-apple.systempreferences:com.apple.Wallpaper-Settings.extension"),
        ("Desktop & Dock", "x-apple.systempreferences:com.apple.Desktop-Settings.extension"),
        ("Control Centre", "x-apple.systempreferences:com.apple.ControlCenter-Settings.extension"),
        ("Lock Screen", "x-apple.systempreferences:com.apple.Lock-Screen-Settings.extension"),
        ("Battery", "x-apple.systempreferences:com.apple.Battery-Settings.extension"),
        ("Trackpad", "x-apple.systempreferences:com.apple.Trackpad-Settings.extension"),
        ("Mouse", "x-apple.systempreferences:com.apple.Mouse-Settings.extension"),
        ("Keyboard", "x-apple.systempreferences:com.apple.Keyboard-Settings.extension"),
        ("Accessibility", "x-apple.systempreferences:com.apple.Accessibility-Settings.extension"),
        ("Siri", "x-apple.systempreferences:com.apple.Siri-Settings.extension"),
        ("Spotlight", "x-apple.systempreferences:com.apple.Spotlight-Settings.extension"),
        ("Date & Time", "x-apple.systempreferences:com.apple.Date-Time-Settings.extension"),
        ("Bluetooth", "x-apple.systempreferences:com.apple.BluetoothSettings"),
        ("Wi-Fi", "x-apple.systempreferences:com.apple.wifi-settings-extension"),
        ("Notifications", "x-apple.systempreferences:com.apple.Notifications-Settings.extension"),
        ("General", "x-apple.systempreferences:com.apple.systempreferences.GeneralSettings"),
        ("Network", "x-apple.systempreferences:com.apple.Network-Settings.extension"),
        ("Screen Time", "x-apple.systempreferences:com.apple.Screen-Time-Settings.extension"),
        ("Energy Saver", "x-apple.systempreferences:com.apple.Battery-Settings.extension"),
        ("Sound Effects", "x-apple.systempreferences:com.apple.Sound-Settings.extension"),
    ]

    for title, uri in settings_panels:
        if manager.count >= manager.target_count:
            break
        subprocess.run(["open", uri], check=False)
        time.sleep(0.4)
        manager.capture_state("System Settings", f"System Settings panel: {title}", "settings_forms_and_dialogs")

    # =========================================================================
    # STRATUM 2: Finder (Folders, Views, Selections x 2 = ~80 screens)
    # =========================================================================
    print("\n--- Capturing Stratum 2: Finder & Desktop ---")
    finder_folders = [
        ("Applications", "/Applications"),
        ("System Applications", "/System/Applications"),
        ("Utilities", "/Applications/Utilities"),
        ("System Library", "/System/Library"),
        ("Library", "/Library"),
        ("User Desktop", str(Path.home() / "Desktop")),
        ("User Documents", str(Path.home() / "Documents")),
        ("User Downloads", str(Path.home() / "Downloads")),
    ]

    view_commands = [
        ("Icon View", 'tell application "System Events" to tell process "Finder" to keystroke "1" using command down'),
        ("List View", 'tell application "System Events" to tell process "Finder" to keystroke "2" using command down'),
        ("Column View", 'tell application "System Events" to tell process "Finder" to keystroke "3" using command down'),
        ("Gallery View", 'tell application "System Events" to tell process "Finder" to keystroke "4" using command down'),
    ]

    for name, path in finder_folders:
        if manager.count >= manager.target_count:
            break
        subprocess.run(["open", path], check=False)
        time.sleep(0.4)
        run_osascript('tell application "Finder" to activate')
        for view_name, cmd in view_commands:
            if manager.count >= manager.target_count:
                break
            run_osascript(cmd)
            time.sleep(0.3)
            # select first item
            run_osascript('tell application "System Events" to tell process "Finder" to key code 125') # down arrow
            time.sleep(0.2)
            manager.capture_state("Finder", f"Finder in {name} with {view_name} (item selected)", "finder_and_desktop")

    # =========================================================================
    # STRATUM 1: Web Browsers (Safari & Chrome) x 2 = ~120 screens
    # =========================================================================
    print("\n--- Capturing Stratum 1: Safari & Chrome ---")
    urls = [
        ("Python Wikipedia", "https://en.wikipedia.org/wiki/Python_(programming_language)"),
        ("AI Wikipedia", "https://en.wikipedia.org/wiki/Artificial_intelligence"),
        ("Computer Science Wikipedia", "https://en.wikipedia.org/wiki/Computer_science"),
        ("Silicon Valley Wikipedia", "https://en.wikipedia.org/wiki/Silicon_Valley"),
        ("Python 3 Documentation", "https://docs.python.org/3/"),
        ("Python Tutorial", "https://docs.python.org/3/tutorial/index.html"),
        ("MDN Web HTML", "https://developer.mozilla.org/en-US/docs/Web/HTML"),
        ("MDN Web CSS", "https://developer.mozilla.org/en-US/docs/Web/CSS"),
        ("GitHub Octocat Spoon-Knife", "https://github.com/octocat/Spoon-Knife"),
        ("GitHub Octocat Issues", "https://github.com/octocat/Spoon-Knife/issues"),
        ("GitHub Octocat Pull Requests", "https://github.com/octocat/Spoon-Knife/pulls"),
        ("Hacker News", "https://news.ycombinator.com/"),
        ("W3Schools HTML", "https://www.w3schools.com/html/"),
        ("W3Schools CSS", "https://www.w3schools.com/css/"),
        ("W3Schools Python", "https://www.w3schools.com/python/"),
    ]

    for app in ["Safari", "Google Chrome"]:
        subprocess.run(["open", "-a", app], check=False)
        time.sleep(0.5)
        for title, url in urls:
            if manager.count >= manager.target_count:
                break
            # Open URL in browser
            if app == "Safari":
                run_osascript(f'tell application "Safari" to set URL of current tab of front window to "{url}"')
            else:
                subprocess.run(["open", "-a", "Google Chrome", url], check=False)
            time.sleep(1.0)
            
            # Capture top of page
            manager.capture_state(app, f"{app} viewing {title} (top of page)", "browser_interface_and_web_content")
            
            # Scroll down and capture
            run_osascript(f'tell application "System Events" to tell process "{app}" to key code 121') # Page Down
            time.sleep(0.3)
            manager.capture_state(app, f"{app} viewing {title} (scrolled down)", "browser_interface_and_web_content")

    # =========================================================================
    # STRATUM 6: Communication & Media (App Store, Music, TV, Podcasts, Weather, Calculator, Calendar, Clock, Stocks, Maps, Font Book) x 2 = ~250 screens
    # =========================================================================
    print("\n--- Capturing Stratum 6: Native System & Utility Applications ---")
    
    # Calculator
    subprocess.run(["open", "-a", "Calculator"], check=False)
    time.sleep(0.5)
    calc_modes = [
        ("Basic", "1"),
        ("Scientific", "2"),
        ("Programmer", "3")
    ]
    for mode_name, key in calc_modes:
        if manager.count >= manager.target_count:
            break
        run_osascript(f'tell application "System Events" to tell process "Calculator" to keystroke "{key}" using command down')
        time.sleep(0.3)
        run_osascript('tell application "System Events" to tell process "Calculator" to keystroke "3.14159*250="')
        time.sleep(0.2)
        manager.capture_state("Calculator", f"Calculator in {mode_name} mode with result", "communication_and_media")

    # Calendar
    subprocess.run(["open", "-a", "Calendar"], check=False)
    time.sleep(0.5)
    cal_views = [
        ("Day View", "1"),
        ("Week View", "2"),
        ("Month View", "3"),
        ("Year View", "4")
    ]
    for view_name, key in cal_views:
        if manager.count >= manager.target_count:
            break
        run_osascript(f'tell application "System Events" to tell process "Calendar" to keystroke "{key}" using command down')
        time.sleep(0.3)
        manager.capture_state("Calendar", f"Calendar in {view_name}", "communication_and_media")

    # Activity Monitor
    subprocess.run(["open", "-a", "Activity Monitor"], check=False)
    time.sleep(0.6)
    act_tabs = [
        ("CPU Tab", "1"),
        ("Memory Tab", "2"),
        ("Energy Tab", "3"),
        ("Disk Tab", "4"),
        ("Network Tab", "5")
    ]
    for tab_name, key in act_tabs:
        if manager.count >= manager.target_count:
            break
        run_osascript(f'tell application "System Events" to tell process "Activity Monitor" to keystroke "{key}" using command down')
        time.sleep(0.3)
        manager.capture_state("Activity Monitor", f"Activity Monitor {tab_name}", "communication_and_media")

    # Clock
    subprocess.run(["open", "-a", "Clock"], check=False)
    time.sleep(0.5)
    for i in range(1, 5):
        if manager.count >= manager.target_count:
            break
        run_osascript(f'tell application "System Events" to tell process "Clock" to keystroke "{i}" using command down')
        time.sleep(0.3)
        manager.capture_state("Clock", f"Clock tab {i}", "communication_and_media")

    # Stocks
    subprocess.run(["open", "-a", "Stocks"], check=False)
    time.sleep(0.6)
    for _ in range(5):
        if manager.count >= manager.target_count:
            break
        run_osascript('tell application "System Events" to tell process "Stocks" to key code 125') # down arrow
        time.sleep(0.4)
        manager.capture_state("Stocks", "Stocks ticker inspection", "communication_and_media")

    # Maps
    locations = [
        ("San Francisco", "maps://?q=San+Francisco"),
        ("New York", "maps://?q=New+York"),
        ("London", "maps://?q=London"),
        ("Tokyo", "maps://?q=Tokyo"),
        ("Paris", "maps://?q=Paris"),
    ]
    for city, uri in locations:
        if manager.count >= manager.target_count:
            break
        subprocess.run(["open", uri], check=False)
        time.sleep(1.0)
        manager.capture_state("Maps", f"Apple Maps viewing {city}", "communication_and_media")

    # App Store
    subprocess.run(["open", "-a", "App Store"], check=False)
    time.sleep(0.8)
    for _ in range(6):
        if manager.count >= manager.target_count:
            break
        run_osascript('tell application "System Events" to tell process "App Store" to key code 125')
        time.sleep(0.4)
        manager.capture_state("App Store", "App Store featured showcase", "communication_and_media")

    # Podcasts
    subprocess.run(["open", "-a", "Podcasts"], check=False)
    time.sleep(0.8)
    for _ in range(5):
        if manager.count >= manager.target_count:
            break
        manager.capture_state("Podcasts", "Apple Podcasts explore and library", "communication_and_media")
        time.sleep(0.4)

    # Music & TV
    for media_app in ["Music", "TV"]:
        subprocess.run(["open", "-a", media_app], check=False)
        time.sleep(0.8)
        for _ in range(4):
            if manager.count >= manager.target_count:
                break
            manager.capture_state(media_app, f"{media_app} application interface", "communication_and_media")
            time.sleep(0.4)

    # Font Book
    subprocess.run(["open", "-a", "Font Book"], check=False)
    time.sleep(0.6)
    for _ in range(6):
        if manager.count >= manager.target_count:
            break
        run_osascript('tell application "System Events" to tell process "Font Book" to key code 125')
        time.sleep(0.3)
        manager.capture_state("Font Book", "Font Book typography inspector", "communication_and_media")

    # =========================================================================
    # STRATUM 3: Editor & Terminal (VS Code, TextEdit, Terminal) x 2 = ~150 screens
    # =========================================================================
    print("\n--- Capturing Stratum 3: Editor & Terminal ---")
    
    # TextEdit
    sample_files = [
        "/Users/harshit/Desktop/YC/screen_understanding/dataset/GEMINI_DATASET_PLAN.md",
        "/Users/harshit/Desktop/YC/screen_understanding/dataset/PILOT_AUTOMATION_REVIEW.md",
        "/Users/harshit/Desktop/YC/screen_understanding/dataset/pilot_v001/PILOT_REPORT.md",
    ]
    for sf in sample_files:
        if manager.count >= manager.target_count:
            break
        subprocess.run(["open", "-a", "TextEdit", sf], check=False)
        time.sleep(0.6)
        manager.capture_state("TextEdit", f"TextEdit viewing {Path(sf).name} top", "editor_and_terminal")
        run_osascript('tell application "System Events" to tell process "TextEdit" to key code 121') # Page down
        time.sleep(0.3)
        manager.capture_state("TextEdit", f"TextEdit viewing {Path(sf).name} scrolled", "editor_and_terminal")

    # Terminal with benign read-only commands
    subprocess.run(["open", "-a", "Terminal"], check=False)
    time.sleep(0.5)
    terminal_commands = [
        "uptime",
        "uname -a; sw_vers",
        "cal -y",
        "df -h",
        "ps aux | head -n 25",
        "ls -lah /Applications | head -n 30",
        "git status",
        "git log --oneline -n 15",
        "python3 --version; python3 -c 'import sys; print(sys.path)'",
        "echo '=== System Activity ==='; vm_stat",
        "netstat -rn | head -n 25",
        "top -l 1 | head -n 25",
    ]
    for tcmd in terminal_commands:
        if manager.count >= manager.target_count:
            break
        run_osascript(f'tell application "Terminal" to do script "{tcmd}" in front window')
        time.sleep(0.5)
        manager.capture_state("Terminal", f"Terminal running: {tcmd}", "editor_and_terminal")

    # Visual Studio Code
    subprocess.run(["open", "-a", "Visual Studio Code", "/Users/harshit/Desktop/YC"], check=False)
    time.sleep(0.8)
    for _ in range(6):
        if manager.count >= manager.target_count:
            break
        manager.capture_state("Visual Studio Code", "VS Code IDE workspace view", "editor_and_terminal")
        time.sleep(0.4)

    # =========================================================================
    # STRATUM 5: Documents, PDFs & Tables (Preview, Numbers, Pages, Keynote) x 2 = ~150 screens
    # =========================================================================
    print("\n--- Capturing Stratum 5: Documents, PDFs & Tables ---")
    
    # Preview with PDFs / Images
    preview_targets = [
        "/Users/harshit/.gemini/antigravity-ide/brain/a1f3fc28-d251-40c9-8a96-879d5e55620b/scratch/whitepaper.pdf",
        "/Users/harshit/.gemini/antigravity-ide/brain/a1f3fc28-d251-40c9-8a96-879d5e55620b/scratch/test.pdf",
    ]
    for pt in preview_targets:
        if Path(pt).exists():
            subprocess.run(["open", "-a", "Preview", pt], check=False)
            time.sleep(0.6)
            for page in range(1, 6):
                if manager.count >= manager.target_count:
                    break
                manager.capture_state("Preview", f"Preview viewing {Path(pt).name} page {page}", "documents_pdfs_and_tables")
                run_osascript('tell application "System Events" to tell process "Preview" to key code 121') # page down
                time.sleep(0.3)

    # Numbers / Pages / Keynote Template Choosers
    for doc_app in ["Numbers", "Pages", "Keynote"]:
        subprocess.run(["open", "-a", doc_app], check=False)
        time.sleep(0.8)
        for _ in range(4):
            if manager.count >= manager.target_count:
                break
            manager.capture_state(doc_app, f"{doc_app} document template chooser", "documents_pdfs_and_tables")
            time.sleep(0.4)

    # =========================================================================
    # Multi-pass loop if target not yet reached
    # =========================================================================
    print(f"\nProgress so far: {manager.count}/{manager.target_count}. Cycling remaining safe states...")
    pass_idx = 1
    while manager.count < manager.target_count:
        pass_idx += 1
        # Alternate between Finder, System Settings, Safari, and Terminal
        for name, path in finder_folders:
            if manager.count >= manager.target_count:
                break
            subprocess.run(["open", path], check=False)
            time.sleep(0.3)
            run_osascript('tell application "System Events" to tell process "Finder" to key code 125')
            time.sleep(0.2)
            manager.capture_state("Finder", f"Finder {name} pass {pass_idx}", "finder_and_desktop")

        for title, uri in settings_panels[:10]:
            if manager.count >= manager.target_count:
                break
            subprocess.run(["open", uri], check=False)
            time.sleep(0.3)
            manager.capture_state("System Settings", f"Settings {title} pass {pass_idx}", "settings_forms_and_dialogs")

        for title, url in urls[:8]:
            if manager.count >= manager.target_count:
                break
            subprocess.run(["open", "-a", "Safari", url], check=False)
            time.sleep(0.6)
            run_osascript('tell application "System Events" to tell process "Safari" to key code 121')
            time.sleep(0.2)
            manager.capture_state("Safari", f"Safari {title} pass {pass_idx}", "browser_interface_and_web_content")

        for tcmd in terminal_commands[:6]:
            if manager.count >= manager.target_count:
                break
            run_osascript(f'tell application "Terminal" to do script "{tcmd}" in front window')
            time.sleep(0.4)
            manager.capture_state("Terminal", f"Terminal {tcmd} pass {pass_idx}", "editor_and_terminal")

    manager.close()
    print(f"\nSUCCESS! Completed {manager.count} screenshots at {datetime.datetime.now()}.")

    # Generate summary.json
    stats: Dict[str, Any] = {
        "total_screenshots": manager.count,
        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "by_stratum": {},
        "by_app": {},
        "by_capture_type": {"window": 0, "fullscreen": 0}
    }
    with open(MANIFEST_PATH, "r") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            st = rec.get("stratum", "unknown")
            app = rec.get("app_name", "unknown")
            ctype = rec.get("capture_type", "unknown")
            stats["by_stratum"][st] = stats["by_stratum"].get(st, 0) + 1
            stats["by_app"][app] = stats["by_app"].get(app, 0) + 1
            stats["by_capture_type"][ctype] = stats["by_capture_type"].get(ctype, 0) + 1

    with open(SUMMARY_PATH, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"Summary written to {SUMMARY_PATH}")


if __name__ == "__main__":
    run_campaign()
