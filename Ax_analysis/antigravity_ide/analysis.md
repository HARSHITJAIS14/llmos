# Antigravity IDE — Accessibility Tree Analysis

**Bundle:** `com.google.antigravity-ide` · **PID:** 10858 · **Capture mode:** `activated` (app had to be foregrounded to get anything)

## What it's built with

Unambiguous Electron. Bundle evidence: the main executable is literally `Contents/MacOS/Electron`, and the frameworks directory contains `Electron Framework.framework`, `Squirrel.framework` (Electron auto-updater), `Mantle.framework`, `ReactiveObjC.framework`, plus the standard four-helper split (GPU / Plugin / Renderer / Helper). This is Google's Antigravity IDE, a VS Code (Code-OSS) derivative — the tree shape confirms Chromium's renderer-side AX bridge.

Tree-shape evidence: a single `webarea` node buried under ~7 layers of anonymous `group` wrappers, all sharing the identical full-window bounds (2560×1410) — the classic Chromium AX scaffolding. One node carries a `native_id` of kind `ax_dom_identifier` (a DOM UUID), proving the fragments we do see are surfaced from the Blink accessibility tree, not AppKit.

## What the tree exposes

Almost nothing. The **full** capture of the entire IDE window is **22 nodes total** (15,873 bytes for a full IDE — a native app of this complexity would be tens of thousands of nodes):

- Roles histogram: 15 `group`, 3 `button`, 2 `list`, 1 `webarea`, 1 `window`. Max depth 11.
- **3 buttons, all unnamed** — geometry (16×16 px at the window's top-left corner) identifies them as the macOS traffic-light close/minimize/zoom controls, i.e. the window chrome, not app UI.
- The only *named* interactive elements are two `list` nodes labeled "Typeahead menu", both zero-height and flagged `offscreen` — dormant editor autocomplete husks.
- **5 truncated containers**: groups with `children_count` of 1–4 whose children were never materialized. One of them (children_count: 2, carrying the DOM identifier, bounds ≈ the right half of the window) is presumably a major panel — its contents are simply absent.
- **Zero value-bearing nodes.** No textfields, no editor content, no tab strip, no file explorer, no status bar, no menus. The tens of thousands of DOM elements in a VS Code-family workbench are invisible.
- Actions present are generic Chromium boilerplate (`RightClick`, `ScrollTo`, `SetFocus`, `Click` on the chrome buttons) — technically "semantic actions", but attached to anonymous groups and window chrome, so functionally useless.
- Interactive nodes with bounds: 5/5 (100%) — but several "bounds" are degenerate (height 0, width 1, parked at y=1440 just below the screen edge).

`surfaces.json` reports an **empty surfaces list** — no secondary AX surfaces at all.

## Ghost windows

`windows.json` lists **10 windows**, only 1 visible. The other 9 are invisible husks: several 2560×30 strips at the top of the screen, four identical 1280×29 slivers parked entirely off-screen at x=2560, and a 64×64 tile. These are Electron's hidden utility/overlay windows (tooltips, menu bar shims, notification layers). A CUA agent enumerating windows here must filter on `visible: true` or it will chase phantoms. Even the "best" visible window reports CG bounds of 178×161 at one screen corner while its AX tree claims 2560×1410 — the window-server and AX geometries disagree, another Electron quirk.

Note also the reported window/tree title is elided with a Unicode ellipsis ("…") — Chromium truncates long workspace titles at the AX layer, so exact-title matching will fail.

## What a CUA agent can and cannot do via pure AX

**Can:** raise/focus the window; close/minimize/zoom via the three unnamed chrome buttons (identified only by position); detect the workspace name (truncated) from the window title; drive the app blind via the native menu bar and keyboard shortcuts.

**Cannot:** see or touch anything inside the IDE — no editor text, no file tree, no tabs, no terminal, no command palette, no chat/agent panel. No values to read, no named targets to click. Pure-AX task completion inside the workbench is effectively impossible in this captured state.

**Caveat:** Chromium/VS Code apps normally *inflate* their AX tree once assistive-technology use is detected (e.g. after `AXManualAccessibility` is set on the app, or VoiceOver pings it). This 22-node husk is what you get without that handshake. A follow-up capture after setting `AXManualAccessibility=true` (or launching with `--force-renderer-accessibility`) may yield a dramatically richer web-native tree and is the first thing to try before writing the app off.

## Reach strategy

1. **Keyboard macro (primary):** VS Code lineage means everything is reachable via Cmd+Shift+P command palette, Cmd+P quick-open, and stable chords. This is the reliable path and needs no AX fidelity at all — only focus.
2. **CDP (strong secondary):** as Electron, it can be started with `--remote-debugging-port` to expose the full DOM over Chrome DevTools Protocol.
3. **AX-inflation retry:** set `AXManualAccessibility` and re-snapshot before falling back further.
4. **Vision + coordinates (fallback):** for confirming state when the above are unavailable.
Pure semantic-AX targeting is off the table on this evidence.

## Verdict

Antigravity IDE presents the canonical **electron-veil**: a Chromium `webarea` husk wrapped in seven anonymous full-window groups, with five truncated containers hiding whatever real content exists, zero named app controls, zero readable values, and a flock of nine invisible ghost windows around one real one. Fidelity is 2/10 — the only points earned are for bounds on the handful of nodes that exist and for nominal action verbs on the window chrome. An agent should not attempt semantic AX automation here; it should drive the app through the command palette / keyboard layer, attempt the `AXManualAccessibility` inflation handshake for observability, and reach for CDP when full programmatic control is required.
