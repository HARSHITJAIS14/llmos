# Discord — AX Tree Analysis

## What it is built with

**Bundle evidence** (`meta.json`): `com.hnc.Discord` ships `Electron Framework.framework`, `Squirrel.framework` (Electron auto-updater), `Mantle.framework`, `ReactiveObjC.framework`, and the four canonical Chromium helper apps (`Discord Helper`, `(GPU)`, `(Renderer)`, `(Plugin)`). The capture tool's own hint list says `electron`. This is a stock Electron app.

**Tree-shape evidence**: the window's content is one `webarea` node (named after the current view) sitting under ~7 levels of anonymous wrapper `group`s — the classic Chromium AX bridge shape. Inside the webarea the DOM leaks through in fragments: two nodes carry `ax_dom_identifier` values (`app-mount`, `popover-portal`), which are Discord's well-known React root and portal container DOM ids. Everything else is unnamed `group`s.

## What the tree exposes

- **25 nodes total**, max depth 10. Roles histogram: 19 `group`, 3 `button`, 1 `window`, 1 `webarea`, 1 `image`.
- Only **3 named nodes**, all structural: the window, one wrapper group, and the webarea — each just echoing the window/view title.
- **3 interactive nodes** (buttons), all with tight, real bounds (16x16 px at the window's top-left corner): these are the macOS traffic-light window controls, and **none of them are named**.
- Actions are plentiful in form but empty in substance: `Click`, `RightClick`, `ScrollTo`, `SetFocus` appear on 24/25 nodes — but they are attached to anonymous full-window groups, not to anything a task could target.
- **Zero value attributes** anywhere; no textfields, lists, links, or text nodes at all.
- **2 truncated containers** (`children_count` > 0 with children missing) inside the webarea — the bridge stops enumerating almost immediately.
- Bounds inside the webarea are degenerate: most groups claim the exact full window rect (1248x918), several report 1x1 px, and one portal group is 0-height and offscreen. Geometry is unusable for targeting.

## What the tree hides

Everything that matters. The entire application UI — server rail, channel/DM list, member list, message history, the composer textfield, every toolbar button — is invisible to AX. The app was on a main view with a fully rendered interface; the AX bridge surfaces none of it. There are no conversation cells, no message text, no input field: the webarea is a husk. `surfaces.json` reports **zero surfaces**.

## Quirks

- **Ghost windows**: 9 AX windows reported, but 8 are invisible 29-30 px-tall title-bar-strip phantoms (four parked offscreen at x=2560, four pinned across the top of the screen at y=0), all titled with just the app name. Only 1 window is real and visible. Any window enumeration must filter on `visible` + plausible height or it will pick a phantom.
- **Skeleton == full**: the skeleton capture (780 B) and the "full" capture (4.5 KB) describe essentially the same husk; going deeper buys nothing.
- Capture mode was `activated` and the app was **not previously running** (`was_running: false`) — so this husk is what you get even with the app frontmost and freshly launched. Chromium only builds a real AX tree when it detects an assistive client; Electron apps additionally gate this behind the `AXManualAccessibility` attribute. Discord evidently did not flip renderer accessibility on for this capture. Setting `AXManualAccessibility=true` on the app element may materialize the web content, but that is untested here.
- The unnamed 16x16 buttons at the top-left are the close/minimize/zoom traffic lights (one accepts `RightClick` — the zoom button's option menu).

## What a CUA agent can and cannot do via pure AX

**Can**: focus/raise the window, close/minimize/zoom it via the three anonymous corner buttons (identifiable only by position), read the current view name from the window title (the title updates per view), and confirm the window's overall bounds.

**Cannot**: find or click any in-app control, read any message or list, type into the composer, navigate servers/channels, or verify any action's outcome. There is no semantic loop possible — observe, act, and verify all fail inside the webarea.

## Reach strategy

1. **First try the AXManualAccessibility unlock** (set the attribute on the app's AX element, then re-snapshot). If Discord's Chromium tree materializes, it may upgrade to web-native quality; this is the single highest-leverage experiment.
2. **Keyboard macros** are the practical workhorse today: Discord has a rich, stable hotkey vocabulary (Cmd+K quick switcher to jump to any DM/channel by typed name, Tab/arrow navigation, Enter to send), and the window title provides coarse verification of navigation. Quick-switcher + type + Enter covers the "send a message to X" route with no tree at all.
3. **Vision + coordinate clicks** for anything hotkeys cannot reach (context menus, reactions, settings toggles), using screenshots for verification since AX cannot confirm state.
4. **CDP is not available**: Discord ships without a remote-debugging port and its updater/integrity checks make injecting one hostile territory; do not plan around it.

## Verdict

Discord is a textbook **electron-veil**: a genuine Chromium `webarea` that admits it has children (`children_count` set, DOM ids leaking through) but renders them inaccessible — 25 nodes, zero named interactive elements, zero values, degenerate geometry, plus a flock of eight ghost windows to trip up window pickers. Fidelity 2/10 (bounds exist on the three window-control buttons, and action verbs are technically present, but nothing else on the rubric is met). A pure-AX agent can manage the window and nothing more. The viable route is keyboard-macro driving (quick switcher + typing) with title-bar and vision-based verification, after one attempt to unlock the real tree via `AXManualAccessibility`.
