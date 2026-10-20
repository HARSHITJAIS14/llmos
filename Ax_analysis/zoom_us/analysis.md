# zoom.us (Zoom Workplace) — Accessibility Tree Analysis

**Bundle:** `us.zoom.xos`, v7.0.6 (84834) · **Capture mode:** background (window not visible, not focused at OS level) · **PID:** 25165 · 4 windows enumerated, full tree scoped to "Zoom Workplace" (1280x960).

## What Zoom is actually made of (the deep-dive answer)

Zoom is **not** Electron, not Qt, not Catalyst, and not CEF. The bundle and binary evidence is unambiguous:

- **Main executable** (`Contents/MacOS/zoom.us`) links directly against **Cocoa/AppKit**, Foundation, libobjc, libc++, and a large slab of Swift runtime dylibs — a genuine native macOS process hosting Zoom's own frameworks (`ZoomUnit`, `ZoomKit`, `Prism`, `ZoomSetting`).
- **130 frameworks/bundles** in `Contents/Frameworks`, almost all Zoom-proprietary (`zUI.framework`, `zVideoUI.bundle`, `zPTUI.bundle`, `cmmlib`, `nydus`, per-feature app bundles like `ZoomPhone.app`, `ZoomClips.app`). Zero CEF/Chromium/Electron/Qt artifacts anywhere in the bundle.
- **The historical claim that Zoom uses a custom cross-platform UI kit is CONFIRMED.** `zUI.framework` contains C++ symbols in a `zui::` namespace — `zui::ViewNode`, `zui::ViewRenderObject`, `zui::CaptionNode`, `zui::ImageNode`, `zui::AvatarNode` — plus ObjC bridge classes (`ZUIList`, `ZUIReusableView`, `ZUISceneWin`, `ZUIStackView`). This is a node-based custom render tree (their own widget kit, shared across platforms) drawn via AppKit/CoreGraphics, wrapped in ObjC view classes that **manually publish accessibility**. `Prism.framework` (the newer cross-platform UI layer) links AppKit + WebKit + Metal.
- **Web content is WKWebView, not Chromium**: `zUnifyWebViewApp.framework` links system WebKit. This matches the single `webarea` node found in the tree (an embedded calendar web surface on the Home tab).

So the tree you get is a *hand-built AX facade* over a custom C++ widget kit — which explains both its strengths (rich names, hotkey hints, actions) and its oddities (nonstandard roles).

## What the tree exposes (measured from full.json)

- **67 total nodes**, max depth 9, capture reported `complete: true`, **0 truncated containers** in the full tree (the skeleton shows collapsed `children_count` groups, but the full pass resolves all of them).
- **43/67 nodes named (64%)**; **38 interactive nodes, 29 named (76%)**.
- **Bounds: 38/38 interactive nodes (100%)** — 66 of 67 nodes carry bounds.
- **Actions on 54 nodes**: `Click`, `RightClick`, `SetFocus` (AXPress-equivalents) are consistently exposed. Buttons are directly pressable without coordinates.
- **Values and states are readable**: disabled/readonly states appear correctly; nav-tab containers carry `value` strings mirroring selection state ("selected" is announced in both name and value); a readonly textfield and a readonly combobox expose full content.
- **Names embed keyboard shortcuts** — e.g. search and AI-companion buttons carry their hotkeys (Cmd-E, Shift-Cmd-O) and history-navigation buttons carry Cmd-bracket hints, written out with unicode symbols. A CUA agent can mine these for keyboard macros for free.

## What the tree hides / quirks

1. **`unknown` roles for tab cells (8 nodes).** The 6-item navigation strip (Home / Chat / Canvas / Whiteboards / Clips / More) is a `group` of `unknown`-role containers, each named "X, N of 6" with a nested **unnamed** `button` that is the actual click target. This double-layer pattern (named unknown parent + anonymous inner button) is the signature of zUI's manual AX bridging — target by the parent's name, press the child.
2. **9 unnamed interactive buttons** — six are the inner tab buttons above (name lives on the parent), and three are anonymous trailing buttons at window edge with bounds but no label; those need vision or trial-press to identify.
3. **One embedded `webarea` ("Zoom Calendar")** — a WKWebView inside the Home tab, which *does* expose its DOM through AX (11 children, a readonly date combobox with a fully descriptive name). Web-native quality, not a husk.
4. **Ghost/helper windows:** 4 windows enumerated, all `visible: false` during background capture — the main "Zoom Workplace" window, a bare 500x500 "zoom.us" helper parked at a screen corner, a "Zoom" window and a "Zoom Client Healthcheck" window offscreen (x≈2700, second display coordinates). Window pickers must filter by title, not take the first window.
5. **No husk under background capture.** The window was invisible and unfocused at OS level, yet the full tree resolved completely and the AX window even reports a `focused` state internally. Background automation is viable.
6. **Marketing/upsell banners inject nodes** (a promo textfield + link + close button were present); layouts shift as these appear and disappear — prefer name-based targeting over positional indexing.
7. `surfaces.json` returned an empty surfaces list — no separately-registered AX surfaces beyond the windows.

## Meeting controls (mute / camera / leave)

**Not verifiable in this capture** — no meeting was in progress; only the pre-meeting "Zoom Workplace" home window existed. What the evidence supports: Zoom's zUI kit systematically attaches names, states, hotkey hints, and press actions to its custom widgets, and Zoom ships extensive documented AX/hotkey support (Cmd-Shift-A mute, Cmd-Shift-V video, Cmd-W leave). The in-meeting toolbar is built with the same kit, so the expectation is named, pressable buttons with mute/video state in the name or state field — but a follow-up capture during a live meeting is required to confirm bounds/actions there, and the meeting window is a *separate* window (likely under the conference UI bundles) that must be re-targeted. Note also that the in-meeting toolbar auto-hides; an AX press generally still works, but state should be read fresh before acting.

## What a CUA agent can and cannot do via pure AX

**Can:** navigate all main tabs (press the named `unknown` container or its inner button), open Search/Settings/New-meeting flows, press every toolbar button semantically via `Click`/`SetFocus`, read disabled/selected/readonly state, dismiss banners, drive the embedded calendar webarea, and harvest keyboard shortcuts from element names for fast macro paths. All of this works with the window in the background.

**Cannot (without extra signals):** identify the 3 anonymous edge buttons; verify in-meeting controls (uncaptured); read video-grid contents (rendered video is pixels, not AX); rely on positional indexes across sessions (promo banners reshuffle child order).

## Reach strategy

**Primary: semantic AX** (find-by-name + exposed Click/SetFocus actions) — the tree is complete, named, bounded, and actionable, even in background. **Secondary: keyboard macros** — Zoom is unusually macro-friendly because the AX names advertise the hotkeys, and global meeting hotkeys (mute/video/leave) bypass the UI entirely; this is the most robust path for in-meeting control. **Fallback: vision** only for the few anonymous buttons and for video-content questions. Coordinate clicking and CDP are unnecessary (no Chromium; the one webview is WKWebView, already AX-visible).

## Verdict

Zoom Workplace is a native AppKit process rendering through a proprietary cross-platform C++ widget kit (`zui::` / Prism) — the old "custom UI kit" reputation is confirmed by symbol-level evidence — yet its accessibility story is far better than that pedigree usually implies: the kit hand-publishes a compact, fully-bounded, action-rich AX tree with hotkeys embedded in names, resolves completely under background capture, and even its embedded WKWebView surfaces are readable. The gaps are cosmetic-but-real: nonstandard `unknown` roles on tab cells, a handful of anonymous buttons, and an unverified (separate-window) in-meeting surface. Rated **native-partial, fidelity 8/10**: a semantic-AX-first agent with keyboard-hotkey macros as the in-meeting workhorse can automate Zoom reliably in pure AX, reserving vision for the last few unlabeled pixels.
