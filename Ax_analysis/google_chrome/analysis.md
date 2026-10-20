# Google Chrome — Accessibility Tree Analysis

**Bundle:** `com.google.Chrome` · **Capture mode:** background (app was not running; launched for capture, pid 25787) · **Errors:** none

## What it's built with

Bundle evidence: the only embedded framework is `Google Chrome Framework.framework` — no Electron, Qt, Flutter, or Catalyst hints. This is Chromium's own stack: the browser chrome (toolbar, tab strip, omnibox, bookmarks bar, infobars) is rendered by Chromium **Views**, a custom C++ widget toolkit that bridges into macOS AX via NSAccessibility, and page content lives in a Blink renderer exposed through a `webarea` node.

Tree-shape evidence agrees: the roles histogram is dominated by generic `group` (21 of 51) with deeply nested single-child wrappers (max depth 10) — the classic Views bridging pattern, not AppKit's flat NSToolbar/NSButton shape. Web content nodes carry `native_id` of kind `ax_dom_identifier`, confirming a Blink AX bridge under the `webarea`.

## Metrics (full.json, window w-28145 "New tab")

- **Total nodes:** 51, max depth 10, `complete: true` at the envelope level
- **Named nodes:** 26/51 (51%)
- **Interactive nodes:** 20 (14 button, 3 combobox, 1 textfield, 1 link, 1 radiobutton) — **17/20 named (85%)**; the 3 unnamed are the 16×16 window traffic-light buttons floating at window level
- **Bounds:** 20/20 interactive nodes have pixel bounds (100%); bounds are sane and screen-anchored
- **Truncated containers:** 2 — both inside the `webarea`: a "content" group with `children_count: 10` and a background-image group with `children_count: 1`, children not serialized
- **Values/states:** partial. States are rich (`disabled` on Back/Forward, `checked`/`selected` + `value: "true"` on the active tab, `focused` on the webarea, `offscreen` flags). A `statictext` carries its value. The omnibox textfield exposes no `value` key (it was empty on a fresh New Tab, so absence is ambiguous)
- **Semantic actions:** extensive — `Click`, `RightClick`, `SetValue`, `TypeText`, `SetFocus`, `Select`, `Expand`/`Collapse`, `Toggle`, `ScrollTo` appear on 46/51 nodes. The omnibox supports `SetValue` + `TypeText` directly

## Skeleton vs full — the lazy-AX husk

skeleton.json (868 bytes) is a **husk**: window → 3 unnamed group wrappers with `children_count: 1` truncation, plus 3 unnamed buttons. full.json (deep traversal) got the entire browser chrome, fully named. This is Chromium's well-known behavior of enabling accessibility lazily — a shallow probe sees almost nothing; a client that walks the tree wakes the bridge up. Renderer (web content) AX stayed mostly asleep even in the full pass: the New Tab page's DOM containers report `children_count` but no children.

## Window zoo

windows.json lists **14 windows**, only 1 visible/real (the 1249×923 browser window). The rest are ghost surfaces: two 1×1 windows at origin, several 2560×30 / 1280×29 strips (status-bubble and fullscreen-toolbar shells) parked at screen edges or offscreen at x=2560, and a hidden 500×500 window. A CUA agent must filter on `visible: true` or it will target phantoms. surfaces.json is empty (no sheets/popovers at capture time).

## What a CUA agent can and cannot do via pure AX

**Can:** everything in the browser chrome, semantically. Navigate (Back/Forward/Reload buttons, all named, disabled-state readable), type a URL or query (omnibox is a named `textfield` with `SetValue`/`TypeText` — the highest-leverage single control in the app), open/close/switch tabs (tab strip is a `tablist` of radiobutton-tabs with selection state, New-tab button, Tab-search combobox), use the bookmarks bar, dismiss infobars, open the Chrome menu and profile/Extensions comboboxes. Full navigation loop = focus omnibox → TypeText → Return, all in-tree.

**Cannot (reliably, in this capture):** read or operate **web page content**. The `webarea` exists and is focused, but its DOM subtree is truncated behind lazy renderer AX. On real pages the content tree can also be enormous once it does hydrate.

## Reach strategy

1. **Semantic AX** for all browser-chrome operations — first choice, high fidelity.
2. **Nudge-then-retry** for page content: a deep AX walk (or Chromium's enhanced-AX activation) typically hydrates the webarea; re-snapshot after touching it.
3. **CDP (Chrome DevTools Protocol)** is the definitive escape hatch for in-page work — Chrome is the one app where a full DOM/JS channel exists; prefer it over vision for anything inside the viewport.
4. **Keyboard macros** (Cmd+L, Cmd+T, Cmd+W, Cmd+1..9) as a robust fallback that sidesteps the tree entirely.
5. Coordinates/vision only as last resort — bounds are complete, so coordinate fallback is at least safe.

## Notable quirks

- 13 of 14 windows are invisible ghosts (1×1 pixels, offscreen strips) — filter by visibility.
- Skeleton probe returns a near-empty husk; the tree only materializes under deep traversal (lazy AX activation).
- Traffic-light buttons are unnamed and float as direct window children, outside the content hierarchy.
- Tabs are exposed as `radiobutton` inside a `tablist` (not `tab` role), with checked/selected states.
- `ax_dom_identifier` native ids surface on web-content nodes — useful join keys against CDP.
- Deep single-child `group` wrapper chains (depth 10 for a mostly-empty window) inflate traversal cost; expect far worse on content-heavy pages.
- Window title carries the profile name appended with an en dash.

## Verdict

Chrome is a **web-native** app with an unusually good native shell: the Views-rendered browser chrome is essentially native-perfect (100% bounds, 85% named interactives, rich states, first-class SetValue/TypeText/Click actions), while the web-content half of the app hides behind Chromium's lazy renderer accessibility — present as a `webarea` with DOM identifiers but truncated in this background capture. **Fidelity 7/10.** A pure-AX agent can drive every browser-level task end-to-end and can reach page content only after waking the renderer AX bridge; for anything nontrivial inside the page, CDP is the natural and uniquely available upgrade path. The main operational hazards are the ghost-window zoo and the husk-like shallow snapshots, both diagnosable and filterable rather than blocking.
