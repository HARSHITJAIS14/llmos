"""Built-in intents: the Siri-class tasks that need no model (implementation.md §14.1).

Checked in order. Each produces a normal Plan with typed checks, so it runs through the same
executor, gates, and traces as a planner plan.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from importlib import resources

import AppKit
import Foundation

from .ax.normalize import fold
from .types import AppEntry, Check, Plan, Step

BROWSERS = {"safari": "Safari", "chrome": "Google Chrome", "google chrome": "Google Chrome",
            "brave": "Brave Browser", "firefox": "Firefox", "arc": "Arc", "edge": "Microsoft Edge"}
_BROWSER_RE = "|".join(sorted((re.escape(b) for b in BROWSERS), key=len, reverse=True))

RE_OPEN_SITE_IN = re.compile(rf"^(?:open|go to|visit|load)\s+(?P<site>.+?)\s+(?:on|in|using|with)\s+(?P<browser>{_BROWSER_RE})$")
RE_SEARCH = re.compile(rf"^(?:search(?: for)?|look up|find)\s+(?P<q>.+?)\s+(?:on|in)\s+(?P<site>[a-z0-9.]+?)"
                       rf"(?:\s+(?:on|in|using)\s+(?P<browser>{_BROWSER_RE}))?$")
RE_OPEN = re.compile(r"^(?:open|launch|start|run)\s+(?P<name>.+)$")
RE_NEW = re.compile(r"^(?:open\s+)?(?:a\s+)?new\s+(?P<what>tab|window)(?:\s+(?:in|on)\s+(?P<app>.+))?$")
RE_QUIT = re.compile(r"^(?:quit|close|exit)\s+(?P<app>.+)$")
RE_DOMAIN = re.compile(r"^(?:https?://)?(?P<host>[a-z0-9-]+(?:\.[a-z0-9-]+)+)(?P<path>/\S*)?$")


def _sites() -> dict:
    return json.loads(resources.files("lsfg.data").joinpath("sites.json").read_text())


def normalize_task(task: str) -> str:
    t = fold(task)
    t = re.sub(r"[\s.!?]+$", "", t)
    t = re.sub(r"^(?:please|hey lsfg|lsfg)[,\s]+", "", t)
    return re.sub(r"\s+", " ", t).strip()


def site_info(site: str) -> tuple[str, str] | None:
    """(url, title-or-domain) for a known site name or a domain-looking string."""
    s = site.strip().lower().removeprefix("the ").removeprefix("my ")
    sites = _sites()
    if s in sites:
        return sites[s]["url"], sites[s].get("title", "")
    m = RE_DOMAIN.match(s)
    if m:
        return ("" if s.startswith("http") else "https://") + s, ""
    return None


def default_browser(session) -> AppEntry | None:
    url = AppKit.NSWorkspace.sharedWorkspace().URLForApplicationToOpenURL_(
        Foundation.NSURL.URLWithString_("https://example.com"))
    if url is None:
        return None
    path = str(url.path())
    for e in session.apps.entries:
        if e.path == path:
            return e
    return session.apps.resolve(path.rsplit("/", 1)[-1].removesuffix(".app"))


BROWSER_BUNDLES = frozenset({"com.apple.Safari", "com.google.Chrome", "com.brave.Browser", "org.mozilla.firefox",
                             "company.thebrowser.Browser", "com.microsoft.edgemac", "com.operasoftware.Opera",
                             "com.vivaldi.Vivaldi", "com.apple.SafariTechnologyPreview"})


def last_used_browser(session) -> AppEntry | None:
    """The running browser whose window is highest in the z-order: where the user was just
    browsing, so where they are most likely signed in ("my gmail")."""
    import Quartz
    from .act.apps import sync
    sync()
    browsers = {int(a.processIdentifier()): str(a.bundleIdentifier() or "")
                for a in AppKit.NSWorkspace.sharedWorkspace().runningApplications()
                if str(a.bundleIdentifier() or "") in BROWSER_BUNDLES}
    if not browsers:
        return None
    for option in (Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGWindowListOptionAll):
        for w in Quartz.CGWindowListCopyWindowInfo(option | Quartz.kCGWindowListExcludeDesktopElements,
                                                   Quartz.kCGNullWindowID) or []:
            pid = int(w.get("kCGWindowOwnerPID", 0))
            if pid in browsers and int(w.get("kCGWindowLayer", 0)) == 0:
                return session.apps.by_bundle(browsers[pid])
    return None


def preferred_browser(session) -> AppEntry | None:
    return last_used_browser(session) or default_browser(session)


def _url_checks(app: str, url: str, title: str) -> list[Check]:
    # The goal is "the page is open in that browser". Being in front is best effort: macOS may
    # refuse to switch apps from a background terminal (cooperative activation, E3).
    host = urllib.parse.urlparse(url).netloc.removeprefix("www.")
    checks = [Check("url", app, {"pattern": re.escape(host)}, group=0)]
    if title:
        checks.append(Check("title", app, {"pattern": re.escape(title)}, group=0))
    return checks


def _app_open_checks(app: str) -> list[Check]:
    return [Check("running", app, {}, group=0),
            Check("frontmost", app, {}, group=1), Check("exists", app, {"target": "window"}, group=1),
            Check("exists", app, {"target": "dialog"}, group=1)]


def _open_url_plan(app: str, url: str, title: str, intent: str) -> Plan:
    step = Step(index=0, op="open_url", app=app, params={"url": url}, post=_url_checks(app, url, title))
    return Plan(steps=[step], source=f"intent:{intent}")


def route(task: str, session) -> Plan | None:
    t = normalize_task(task)
    if not t:
        return None

    m = RE_OPEN_SITE_IN.match(t)
    if m:
        info = site_info(m.group("site"))
        browser = session.apps.resolve(BROWSERS[m.group("browser")])
        if info and browser:
            return _open_url_plan(browser.name, info[0], info[1], "open_site")

    m = RE_SEARCH.match(t)
    if m:
        sites = _sites()
        site = m.group("site").removesuffix(".com")
        tmpl = sites.get(site, {}).get("search")
        if tmpl:
            browser = (session.apps.resolve(BROWSERS[m.group("browser")]) if m.group("browser")
                       else preferred_browser(session))
            if browser:
                url = tmpl.replace("{q}", urllib.parse.quote_plus(m.group("q")))
                return _open_url_plan(browser.name, url, "", "search_site")

    m = RE_NEW.match(t)
    if m:
        app = session.apps.resolve(m.group("app")) if m.group("app") else None
        if app is None and not m.group("app"):
            from .act import apps as appsmod
            fm = appsmod.frontmost()
            app = session.apps.by_bundle(fm[0]) if fm else None
        if app is not None:
            what = "New Tab" if m.group("what") == "tab" else "New Window"
            step = Step(index=0, op="menu", app=app.name, params={"path": ["File", what]},
                        post=[Check("running", app.name, {})])
            return Plan(steps=[step], source="intent:new_" + m.group("what"))

    m = RE_QUIT.match(t)
    if m:
        app = session.apps.resolve(m.group("app"))
        if app is not None:
            return Plan(steps=[Step(index=0, op="quit", app=app.name, params={}, risk="safe")],
                        source="intent:quit")

    m = RE_OPEN.match(t)
    if m:
        name = m.group("name")
        app = session.apps.resolve(name)
        if app is not None:
            step = Step(index=0, op="open_app", app=app.name, params={}, post=_app_open_checks(app.name))
            return Plan(steps=[step], source="intent:open_app")
        info = site_info(name)
        if info:
            browser = preferred_browser(session)
            if browser:
                return _open_url_plan(browser.name, info[0], info[1], "open_site")
    return None
