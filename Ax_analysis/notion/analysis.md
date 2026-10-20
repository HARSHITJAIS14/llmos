# Notion — AX Tree Analysis

**Bundle:** `notion.id` · `/Applications/Notion.app` · **Capture mode:** background (`was_running: false`)

## What it's built with

Unambiguous **Electron** app. Bundle evidence: `Electron Framework.framework`, the four Chromium helper apps (`Notion Helper`, `GPU`, `Renderer`, `Plugin`), `Squirrel.framework` (Electron auto-updater), `Mantle`/`ReactiveObjC` glue. Tree evidence corroborates: a deep stack of anonymous `group` wrappers (max depth 11) terminating in Chromium `webarea` nodes carrying `ax_dom_identifier` native ids (`root`, `notion-app`) — the signature shape of a Chromium renderer bridged into macOS AX.

## What the tree exposes

Measured from `full.json` (window-scoped, focused window):

| Metric | Value |
|---|---|
| Total nodes | 19 |
| Named nodes | 4 (window/group titles + two webarea labels: "Tab Bar", the page title) |
| Interactive nodes | 3 buttons — **0 named**, 3/3 with bounds (100%) |
| Truncated containers (`children_count>0`, no children) | 3 (counts 6, 4, 1 — the entire app content) |
| Value-bearing roles / values present | 0 / 0 |
| Roles histogram | group 13, button 3, webarea 2, window 1 |
| Semantic actions | Yes on what exists: Click, RightClick, ScrollTo, SetFocus |

The 3 unnamed 16x16 buttons at the window's top-left are the traffic-light window controls, drawn by Notion itself. The two `webarea` nodes (tab-bar strip, 29px tall; main content, 774px tall) are correctly positioned and even report `focused`, but their subtrees stop dead at groups with `children_count: 6` (tab bar) and `children_count: 4` (app root, DOM id `notion-app`). **Everything a user would interact with — sidebar, page tree, editor blocks, search, toolbar — is behind those truncated containers.** No text fields, no values, no document content reaches AX in this capture.

`surfaces.json` is empty. `windows.json` shows 9 windows: 1 real focused window plus **8 invisible ghost windows** (29–30px strips titled "Notion", parked at screen edges/offscreen) — typical Electron auxiliary shells; a CUA agent must filter to the single visible focused window and ignore the rest.

## Husk behavior

This is the canonical **Electron background husk**: captured with the app in the background, Chromium declines to materialize the renderer accessibility tree, leaving webarea stubs with child counts but no children. Electron hydrates the DOM-to-AX bridge only once an assistive-technology client is detected and the renderer is active (the `AXManualAccessibility` / `AXEnhancedUserInterface` dance). A foreground re-capture after setting that attribute would very likely reveal a rich web-native tree — Notion's DOM carries good ARIA labeling — but **this capture proves the background path is unusable**.

## What a CUA agent can / cannot do via pure AX (as captured)

- **Can:** identify the app, the real window and its bounds; focus the window; click the window controls; right-click/scroll-to the webarea shells.
- **Cannot:** see, name, read, or press any actual Notion UI — no navigation, no page opening, no text entry, no state reading. Zero named interactive elements means zero semantic targeting.

## Reach strategy

1. **First move: foreground the app + set `AXManualAccessibility`/`AXEnhancedUserInterface`, then re-snapshot.** If the webareas hydrate, Notion becomes web-native and semantic reach works.
2. **Keyboard macros** are the strongest reliable channel regardless: Cmd+P / Cmd+K quick-find, Cmd+N new page, plain typing into the focused editor. Focus window → Cmd+P → type → Enter covers most navigation blind.
3. **CDP** viable in principle (Electron) only if launched with a remote-debugging port — not available on a stock launch.
4. **Vision + coordinates** as fallback for hover-revealed affordances (block handles, drag targets) even after hydration.

## Quirks

- 8 ghost/invisible windows per process; only one real window.
- Window title carries a trailing space ("LLM OS ").
- Webareas report `focused` state while their content is withheld.
- `ax_dom_identifier` native ids (`root`, `notion-app`) leak through, confirming the DOM bridge exists but is dormant.
- The action vocabulary (Click/RightClick/ScrollTo/SetFocus) is present — the bridge machinery works; only the subtree is withheld.

## Verdict

**electron-veil, fidelity 2/10 (as captured in background).** Bundle and tree both say Electron, and the tree is the textbook veil: correctly-bounded webarea stubs whose entire content — every real control and all text — sits behind three truncated containers. A pure-AX loop is impossible against this capture. The score reflects only bounds on the 3 trivial buttons and the presence of semantic action verbs; nothing interactive is named, no values exist, and the husk fails both stability criteria. The practical path is: foreground + enable Electron's manual-accessibility flag and re-capture (likely upgrading Notion to web-native), with keyboard-macro driving (Cmd+P command palette) as the dependable workhorse either way.
