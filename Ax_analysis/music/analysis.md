# Apple Music — AX Tree Analysis

## What the app is built with

- **Bundle evidence**: `/System/Applications/Music.app`, bundle id `com.apple.Music`, a first-party system app. The capture's framework scan lists no third-party frameworks and no Electron/Qt/Flutter/Catalyst hints — as expected for a system binary linking Apple frameworks directly.
- **Tree-shape evidence**: the chrome is unmistakably native AppKit/SwiftUI. Nodes carry rich, stable `ax_identifier`s in a SwiftUI-ish dotted style — `Music.accountButton`, `Music.miniPlayer.shuffleButton`, `Music.miniPlayer.playbackTransportControl`, `sidebarScroller`, `outline`. Some identifiers even embed live view state, e.g. `Music.miniPlayer.contentView[viewState=mini,isPlaying=false]` and `metadataRegion[state=empty]` — a strong SwiftUI-with-explicit-accessibility-identifiers signal.
- Apple Music is known to be a hybrid: native sidebar/transport chrome around JET/WebKit content panes (Home, Radio, iTunes Store). This capture corroborates that indirectly: the native chrome is fully articulated while the central content pane contributed **zero** nodes (see below).

## Capture context

- Capture mode: **background**. The app was not previously running (`was_running: false`); one window (`Music`, 980x580), reported `visible: false` and `is_focused: false` — a freshly launched, non-frontmost window.
- All three captures succeeded with no errors. Skeleton is tiny (1.3 KB, 11 nodes), full tree is 27 KB / 47 nodes. Surfaces oddly reports the focused window with `type: "alert"`, and the window root's AX role serializes as `dialog` rather than `window` — a quirk of how Music vends its main window, worth knowing when filtering by surface type.

## Metrics (full.json)

| Metric | Value |
|---|---|
| Total nodes | 47 |
| Named nodes | 38 (81%) |
| Interactive nodes (button/treeitem/cell/outline) | 39 |
| Interactive named | 36 (92%) — the 3 unnamed are the window traffic-light buttons |
| Interactive with bounds | 39 (100%) |
| Truncated containers (full tree) | 0 (skeleton has 2, resolved by the full pass) |
| Nodes with available_actions | 28 (Click, RightClick, Select, Scroll, SetFocus) |
| Value-bearing nodes | 0 (no textfields/sliders present in this capture) |
| Max depth | 6 |
| Roles | button 14, treeitem 12, cell 12, group 6, dialog 1, scrollarea 1, outline 1 |

## What the tree exposes

- **Sidebar (outline)**: a 12-item navigation outline, every row named and clickable with exact bounds — search, home, radio, library sections (recently added / artists / albums / songs), store entries, and playlists, with `expanded` states on the section headers. This is a fully drivable navigation surface.
- **Mini-player transport bar**: shuffle, previous, play, next, repeat, lyrics, queue, AirPlay, volume — all named buttons with bounds, semantic Click actions, and honest `disabled` states (transport controls disabled because nothing is queued; the metadata region identifier itself says `state=empty`).
- **Account button**: a named button carrying the signed-in user's personal name (described abstractly here).
- Actions are semantic (`Click`, `RightClick`, `Select`, `SetFocus`, `Scroll`) — an agent can press elements without synthesizing coordinates.

## What the tree hides

- **The entire main content pane is absent.** 47 nodes for a full Music window is chrome only: no song lists, no album grid, no now-playing metadata, no search field. The center region (a JET/WebKit-rendered view for Home/Radio/Store, or a table view for Library) contributed nothing in this background, non-visible capture. This is the big gap — everything a user actually browses lives there.
- No value-bearing controls surfaced (no volume slider value, no scrub bar, no search textfield), so read-back of playback position/volume via AX is unavailable in this snapshot.
- Whether the content pane appears when the window is frontmost/visible is untested here; expect it to populate (native table views certainly; the web panes may expose an AXWebArea DOM) once the window is actually rendered.

## What a CUA agent can / cannot do via pure AX

**Can**: navigate the sidebar deterministically (click any library section, store, or playlists entry by name), operate every transport control (play/pause/next/shuffle/repeat) when enabled, open lyrics/queue/AirPlay/volume popovers, click the account button — all via semantic Click with verified bounds and disabled-state checks. The stable `ax_identifier`s (`Music.miniPlayer.*`) make routes highly compilable and resilient to layout changes.

**Cannot (from this capture)**: read or click anything in the content area — pick a specific song/album, read the now-playing title, type into search, or scrub. Those require a foreground/visible re-snapshot, and if the content pane is web-backed, possibly per-pane handling.

## Reach strategy

1. **Semantic AX first** for navigation and transport — it is excellent here.
2. **Re-snapshot with the window raised/visible** before any content-area task; treat this background tree as chrome-only.
3. **Keyboard/menu-bar macros** as a strong complement: Music has a full native menu bar (Controls > Play, Cmd+F for search, etc.) — often faster than digging into a web pane.
4. **AppleScript/Scripting Bridge is the ace**: Music is one of the most scriptable apps on macOS (`tell application "Music" to play track ...`), bypassing the AX content gap entirely for playback/library tasks.
5. Vision/coordinates only as a last resort for store/browse web panes if their AX DOM proves thin.

## Notable quirks

- Window root role is `dialog` and the surface list types it as `alert` — filter logic expecting `window` will misclassify Music's main window.
- All sidebar cells report a `focused` state simultaneously — clearly bogus focus reporting; do not trust `focused` on these cells for verification.
- Identifiers leak UI state (`[viewState=mini,isPlaying=false]`, `[hovered=false]`, `[state=empty]`) — useful free telemetry, but exact-match identifier selectors will break as state changes; match on prefix.
- Window was `visible: false` yet yielded a complete chrome tree — background capture is stable for native parts; only the (web/lazy) content pane is a husk.
- Play/Previous/Next honestly report `disabled` when the queue is empty — good for precondition checks.

## Verdict

Apple Music presents a textbook **native-partial** tree in background capture: the AppKit/SwiftUI chrome (sidebar outline + mini-player transport) is near-perfect — fully named, fully bounded, semantically actionable, with truthful disabled states and gold-standard stable accessibility identifiers — but the app's actual content (the browse/library pane, almost certainly JET/WebKit-backed) contributes nothing while the window is unrendered. An agent can navigate and control playback chrome purely through AX today, but any task touching songs, search, or now-playing metadata needs a foreground re-snapshot, menu-bar/keyboard routes, or — best of all for this app — AppleScript, which Music supports more richly than nearly any other macOS application. Fidelity 7/10: docked for the missing content pane and absent values, not for the chrome, which is exemplary.
