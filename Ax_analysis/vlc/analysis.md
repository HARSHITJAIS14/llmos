# VLC — Accessibility Tree Analysis

**Bundle:** `org.videolan.vlc` · `/Applications/VLC.app` · capture mode: **background** (app was not previously running; launched for capture)

## What it's built with

Bundle evidence: frameworks shipped are **Sparkle** (updates), **Growl** (legacy notifications), and **Breakpad** (crash reporting) — the classic fingerprint of a hand-built native Mac app. No Electron, Qt, Flutter, or Catalyst hints. VLC's macOS build uses its dedicated **Cocoa/AppKit interface** (the Qt UI is Windows/Linux only), and the tree shape confirms it: proper `window → group → scrollarea → outline → treeitem/cell` sidebar, real `button`/`slider`/`switch`/`textfield` roles, no `webarea` anywhere.

## Metrics (from full.json, window-scoped)

| Metric | Value |
|---|---|
| Total nodes | 57 |
| Named nodes | 47 (82%) |
| Interactive nodes | 36 |
| Named interactive | 31 (86%) |
| Interactive with bounds | 36 (100%) |
| Truncated containers | 0 (skeleton had 1, resolved in full) |
| Max depth | 5 |
| Roles | 17 button, 15 treeitem, 15 cell, 2 slider, 2 group, 1 each window/textfield/switch/handle/outline/scrollarea |
| Values readable | Yes — sliders expose numeric values (position 0, volume 320), switch exposes 0/1 state |
| Semantic actions | Yes — `Click`, `RightClick`, `Toggle`, `Select`, `SetValue`, `SetFocus`, `Scroll` |

## What the tree exposes

- **Full playback control deck**: named buttons for Play, Next, Forward, Stop, Mute, Full Volume, Repeat, Shuffle, Show/Hide Playlist, Audio Effects, and a Fullscreen `switch` with readable toggle state — every one with bounds and a `Click` (or `Toggle`) action.
- **Two live sliders** (Position, Volume) with current values and `SetValue` — an agent can seek and set volume semantically, no dragging needed.
- **Sidebar outline** with 15 clickable tree items (Playlist, Media Library, local media categories, network discovery sources, internet directories), each with a `Click` action.
- **Playlist search textfield** with a descriptive name and `SetValue`/`SetFocus` — typed search is fully semantic.
- An "Open media..." button in the empty-playlist drop zone.

## What it hides / quirks

- **Ghost windows**: 9 windows reported; 8 are invisible 29–30px-tall strips titled "VLC" (fullscreen-controller / video-out shadow windows VLC pre-creates). Only one real window ("VLC media player") matters — filter by `visible` + title.
- **Window-list bounds lie**: the best-window record reports a 125×157 rect, but the actual AX window frame in the tree is 1280×803. Trust node bounds, not the window list.
- **Sliver buttons**: Repeat, Shuffle, and Audio Effects report only 2px-wide bounds overlapping neighbors — semantic `Click` via the AX action is safe; coordinate clicks on these would miss.
- **5 unnamed buttons**: three ~12×14px title-bar buttons (traffic-light region) and two 2px-wide separator-like buttons. All decorative/window-chrome; every functional control is named.
- **No husk under background capture**: the full tree, values, and actions were captured with the app unfocused — VLC renders its AX tree without needing frontmost status.
- `surfaces.json` is empty (no video surface at capture time); skeleton nodes carry no bounds (capture-tier limitation — full.json has 100% bounds).

## What a CUA agent can / cannot do via pure AX

**Can**: press every transport control by name, seek via `SetValue` on the Position slider, set volume numerically, toggle fullscreen with verifiable state, navigate the sidebar sources, search the playlist by typing, and open media via the "Open media..." button (leading to the standard, fully accessible NSOpenPanel). The observe → act → verify loop closes entirely in AX: slider values and the fullscreen switch state serve as verification signals.

**Cannot / caution**: the video canvas itself is a blank group (expected — a render surface); playlist rows only appear once media is loaded (only the empty-state drop zone was present here). Coordinate-clicking the 2px sliver buttons is unreliable — always prefer the semantic action.

## Reach strategy

**Semantic-first, unconditionally.** Use AX actions (`Click`, `Toggle`, `SetValue`) on named nodes; fall back to VLC's rich global keyboard shortcuts (space, ⌘O, arrow seek, ⌘↑/↓ volume) as a macro layer. Coordinates and vision are unnecessary except perhaps to verify actual video frames rendering.

## Verdict

VLC is a **native-perfect** target. Its hand-written Cocoa interface exposes one of the cleanest small AX trees in the catalog: every functional control named, 100% of interactive nodes bounded, sliders and switches with readable, settable values, zero truncation in the full capture, and full stability under background capture. The only hazards are cosmetic — a swarm of invisible ghost windows to filter out, a misleading window-list rect, and a few 2px sliver buttons that demand semantic clicks over coordinates. A CUA agent can run the complete perceive-act-verify loop here in pure AX. Fidelity: **9/10** (docked only for the unnamed chrome buttons and skeleton-tier bounds/truncation gaps).
