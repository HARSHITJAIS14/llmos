"""E3: which activation methods can bring an app to the front from a background CLI process?
Brings the target app forward several times, then gives focus back to the app that was in front.
Usage: python p6_activation.py [Safari]"""
import subprocess
import sys
import time

import AppKit
import ApplicationServices as AS

target_name = sys.argv[1] if len(sys.argv) > 1 else "Safari"
ws = AppKit.NSWorkspace.sharedWorkspace()


def front():
    a = ws.frontmostApplication()
    return (str(a.localizedName()), int(a.processIdentifier())) if a else ("?", -1)


def running(name):
    for a in ws.runningApplications():
        if str(a.localizedName()) == name:
            return a
    return None


def wait_front(pid, t=1.5):
    t0 = time.monotonic()
    while time.monotonic() - t0 < t:
        if front()[1] == pid:
            return round((time.monotonic() - t0) * 1000)
        time.sleep(0.01)
    return None


orig_name, orig_pid = front()
if orig_name == target_name:                       # need a different app in front for a fair test
    home = running("Finder")
    orig_name, orig_pid = str(home.localizedName()), int(home.processIdentifier())
orig = AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(orig_pid)
app = running(target_name)
if app is None:
    sys.exit(f"{target_name} is not running")
pid = int(app.processIdentifier())


def give_back():
    if orig is not None:
        orig.activateWithOptions_(0)
        subprocess.run(["open", "-b", str(orig.bundleIdentifier())], capture_output=True)
    time.sleep(0.4)


def m_ax():
    AS.AXUIElementSetAttributeValue(AS.AXUIElementCreateApplication(pid), "AXFrontmost", True)


def m_running_activate():
    app.activateWithOptions_(AppKit.NSApplicationActivateAllWindows)


def m_workspace_open():
    cfg = AppKit.NSWorkspaceOpenConfiguration.configuration()
    cfg.setActivates_(True)
    ws.openApplicationAtURL_configuration_completionHandler_(app.bundleURL(), cfg, None)


def m_open_cli():
    subprocess.run(["open", "-b", str(app.bundleIdentifier())], capture_output=True)


print(f"front before: {orig_name}")
for name, fn in [("AXFrontmost", m_ax), ("NSRunningApplication.activate", m_running_activate),
                 ("NSWorkspace.openApplicationAtURL", m_workspace_open), ("open -b (LaunchServices CLI)", m_open_cli)]:
    give_back()
    before = front()[0]
    t0 = time.perf_counter()
    fn()
    ms = wait_front(pid)
    print(f"  {name:<34} from {before:<16} → {'OK in ' + str(ms) + ' ms' if ms is not None else 'did NOT activate'}"
          f"  (call {(time.perf_counter() - t0) * 1000 - (ms or 0):.0f} ms)")
give_back()
print(f"front after: {front()[0]}")
