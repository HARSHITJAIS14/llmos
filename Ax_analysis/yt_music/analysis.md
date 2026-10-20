# YT Music — AX Tree Analysis

## What it is built with

**Not Electron.** The bundle id is `com.apple.Safari.WebApp.4E77B8ED-…` and the executable is the system stub `/System/Library/CoreServices/Web App.app` — this is a **Safari "Add to Dock" Web App** (macOS Sonoma+ WebKit web-app shell). The `frameworks` list is empty and there are no Electron/Qt/Flutter hints because the binary is Apple's own shared shell; all rendering is WebKit, which has first-class AX-DOM bridging. Capture mode was `activated`.

Tree-shape evidence agrees: a thin Safari chrome layer (a `tablist` holding a `BrowserView?IsPageLoaded=true&WebViewProcessID=…` group, a toolbar with `BackForwardSegmentedControl` and `WebAppShareButton`) wrapping a single `webarea` that expands into a full web-content tree with web roles (`link`, `heading`, `navigation`, `search`, `main`, `radiobutton` tab-chips, `slider`, `progressbar`, `switch`) and `ax_dom_identifier` native ids on some nodes.

## Metrics (from full.json, window-scoped)

- **Total nodes:** 437, max depth 10 (depth-capped — see truncation)
- **Named nodes:** 220 (50.3% overall; groups are mostly anonymous, as usual for DOM wrappers)
- **Interactive nodes** (button/link/radiobutton/switch/combobox/slider): **120**, of which **116 named (96.7%)**. The 4 unnamed: one search `combobox` (DOM id `input` — findable anyway) and 3 unlabeled buttons.
- **Bounds:** present on **100%** of nodes (437/437), none zero-sized.
- **Values:** present where they matter — volume `slider` value=100, playback `progressbar` value=98, three `switch`es value=0; 40/41 value-bearing roles carry a value.
- **Semantic actions:** rich and explicit — `Click` (141 nodes), `Toggle` (14), `SetValue` (3), `TypeText` (1, the search field), `Select`, `Expand/Collapse`, `ScrollTo` (423), `SetFocus` (179), `RightClick` (426).
- **Truncated containers:** **177** (children_count>0, children absent) — but **all 177 sit exactly at depth 10**, so this is the capture's depth cap, not the app hiding content. Mostly `group` (106) and `link` (70) leaf-wrappers with 1–3 unexpanded children (likely text/thumbnail internals).
- **States:** 261 nodes flagged `offscreen`, 3 `disabled`. Roles histogram dominated by `group` (266) and `link` (79).

## What the tree exposes / hides

Exposes: the entire YouTube Music web UI — navigation, search field (typeable via `TypeText`/`SetValue`), content shelves of named song/album/artist links, player bar with named transport buttons, seek progressbar with a live value, volume slider with `SetValue`, toggle switches, and per-node bounds throughout. Song/artist strings appear as node names (page title itself is a track title).

Hides: nothing structural. The only gaps are (a) sub-depth-10 grandchildren behind the 177 depth-capped wrappers — re-scoping a snapshot to a subtree recovers them; (b) 3 unnamed icon buttons in the player area, disambiguable by position/description; (c) the many `offscreen`-flagged nodes are simply scrolled out of view — `ScrollTo` is offered on 423 nodes to bring them in.

## Quirks

- **Ghost windows:** 10 windows reported; 9 are invisible shells (2560x30 strips at the menubar, 1280x29 title-bar slivers, a 500x500 phantom). Only `w-27259` is real. A CUA must filter on `visible: true` — the best-window heuristic already picked correctly.
- **Odd best-window bounds:** meta reports the visible window as 125x145 at (2576,1033) while the AX root reports 1280x803 at (2560,565) — the window lives on a secondary display (x ≥ 2560) and the CG-window bounds look like a mini-player/thumbnail artifact. Trust the AX-root bounds for hit-testing, and note coordinates are in extended-desktop space.
- **Skeleton is a chrome husk by design:** skeleton.json (1.3 KB) shows only the Safari web-app chrome with the web content collapsed behind one `BrowserView` group — web content requires the full capture. Background/husk behavior untested (capture was `activated`).
- `surfaces.json` is empty — no extra AX surfaces beyond the window.
- Names include non-English (transliterated Hindi) titles; expect Unicode in match targets.

## What a CUA agent can / cannot do via pure AX

Can: find any control by name/role, click transport buttons semantically (`Click`), toggle switches (`Toggle`), set volume (`SetValue` on the slider), type a query into search (`SetFocus` + `TypeText`), read playback position from the progressbar value, scroll shelves via `ScrollTo`, and verify state after acting. This is a full observe→act→verify loop in pure AX.

Cannot / caveats: content below depth 10 needs a re-scoped snapshot; the 3 unnamed player buttons need positional or description-based disambiguation; no CDP is available (WebKit shell, not Chromium — `WebViewProcessID` is a WebKit content process, not a DevTools endpoint).

## Reach strategy

**Semantic AX first** — names, roles, and actions are all there. Fall back to keyboard (space = play/pause, `/` = search on YT Music) for the unnamed buttons. Coordinates work as backup (100% bounds coverage) but mind the secondary-display offset. Vision and CDP are unnecessary.

## Verdict

YT Music here is not an Electron app but a Safari Web App shell, and WebKit gives it the best-case webview story: a genuine web-native tree with ~97% of 120 interactive elements named, full bounds, readable values on slider/progress/switches, and a rich semantic action set including SetValue and TypeText. The only deductions are the capture-side depth-10 truncation (177 unexpanded leaf wrappers) and a handful of unnamed icon buttons; background-capture stability is unverified since this was an activated capture. Fidelity 8/10, category **web-native** — pure-AX automation is fully viable, with subtree re-snapshots to punch through the depth cap and ghost-window filtering as the only operational hygiene required.
