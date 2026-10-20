# Firefox — AX Tree Analysis

**Bundle:** `org.mozilla.firefox` · `/Applications/Firefox.app/Contents/MacOS/firefox`
**Capture mode:** `activated` (app was not running; it was launched for the capture)
**Best window:** "New Tab" (w-28142) — note the tiny reported bounds (92x108 at 15,775), likely a freshly-restored geometry at capture time.

## What it's built with

Bundle evidence: the only bundled framework is `ChannelPrefs.framework` — no Electron, Qt, Flutter, or Catalyst hints. The executable is Mozilla's own `firefox` binary. This is **Gecko**: Mozilla's custom C++ rendering/widget toolkit with its own hand-rolled macOS accessibility bridge (mozAccessible), not AppKit controls.

Tree-shape evidence confirms it: nearly every node carries a `native_id` of kind `ax_dom_identifier` with values like `nav-bar`, `urlbar`, `back-button`, `PersonalToolbar`, `tabbrowser-tabs`, `PanelUI-menu-button` — these are the XUL/HTML DOM element ids of the browser chrome itself. Firefox exposes its *own UI* through the same DOM-to-AX pipeline it uses for web pages, and page content appears under a `webarea` node. That is the signature of a browser that is web-native all the way down.

## Metrics (full.json, window-scoped, complete=true)

- **Total nodes:** 93 (ref_count 92 + window root), max depth 10
- **Named nodes:** 44/93 (47%) — the unnamed remainder is mostly structural `group`/`splitter`/`toolbar` scaffolding, which is normal
- **Roles histogram:** group 33, button 27, switch 5, splitter 3, toolbar 3, combobox 2, image 2, tablist 2, link 2, heading 2, complementary 2, and 1 each of window, radiobutton, statictext, tabpanel, scrollarea, webarea, article, main, list, alert
- **Interactive nodes:** 37 (buttons, comboboxes, links, radiobutton, switches); **33/37 named (89%)**
  - The 4 unnamed: the search-engine picker combobox (which does carry a readable value) and 3 bare buttons parked directly under the window (almost certainly the traffic-light window controls)
- **Bounds:** 100% of all nodes — every single node, interactive or not, has bounds
- **Values:** present and readable — comboboxes expose their text/placeholder, the tab `radiobutton` reports `checked`+`selected`, all 5 sidebar `switch` nodes report a value, headings report levels
- **States:** disabled (Back/Forward on a fresh tab), focused (URL bar), readonly, checked, selected, offscreen — all correctly surfaced
- **Actions:** 92/93 nodes list `available_actions` (Click, RightClick, ScrollTo, SetFocus) — semantic press-style actions are universally available
- **Truncated containers:** 9 (children_count > 0 with no children) — all inside the New Tab page's webarea (weather widget, shortcuts grid, misc groups) plus one Customize button. This looks like capture-depth limiting / Gecko lazy subtree materialization, not a veil: the webarea itself yielded 28 real, labeled nodes.

## What the tree exposes

- The **entire browser chrome**, fully labeled: navigation toolbar (Sidebars, Back, Forward, Reload, Account, Extensions, List all tabs, app menu), the URL bar (a focused combobox named with its search placeholder), the tab strip as a proper `tablist` with the active tab as a checked/selected radiobutton, and sidebar launcher switches whose names even embed their keyboard shortcuts (e.g. "Open bookmarks (⌘B)").
- A **bookmarks toolbar** of ~9 personal bookmark buttons plus chevron/Other Bookmarks controls (contents are personal page titles; described abstractly here).
- **Page content** under a `webarea` — the New Tab page renders as real semantic web AX: headings, article, links, main, list, complementary regions, with names and bounds.
- **Stable selectors for free:** the `ax_dom_identifier` values (`urlbar`, `back-button`, `PlacesChevron`, ...) are Firefox's internal DOM ids — stable across versions and localizations, ideal anchors for compiled routes.

## What it hides / quirks

- **9 truncated containers** inside the content webarea — deep page subtrees need re-expansion (targeted re-snapshot / ScrollTo + refetch) rather than assuming one snapshot holds the whole page.
- **Multi-process ambiguity:** `surfaces.json` failed with `AMBIGUOUS_TARGET` — 11 processes named "Firefox" (parent + content/GPU/utility children). Any tool that targets by app *name* will trip here; always target by pid/process_instance. Only the parent (pid 25827) owns the AX tree.
- **Ghost window:** a second window "Firefox" (w-28141) with 0x0 bounds at y=1440, invisible — an off-screen placeholder to be filtered out.
- Three unnamed buttons at window level (window controls) and an unnamed search-engine combobox.
- Capture was done with the app **activated**; background-capture stability was not exercised, so husk-on-background is unproven either way (Firefox historically initializes its a11y engine lazily on first AX query).
- Switch values are numeric strings ("0") rather than booleans; heading nodes reuse `value` for heading level.

## What a CUA agent can do via pure AX

Essentially everything: read the full chrome and page structure, click any toolbar/bookmark/tab/link by name or DOM id, focus and type into the URL bar (it is a real focused combobox), read toggle/tab state, right-click for context menus, and ScrollTo elements. Bounds on 100% of nodes mean coordinate fallback is always available but rarely needed.

**Reach strategy:** **semantic-first** — find by name or `ax_dom_identifier`, act with Click/SetFocus. Keyboard macros are an excellent secondary channel (Firefox names even advertise shortcuts). CDP is unnecessary for chrome-level tasks but Firefox does support remote debugging (BiDi/CDP) if deep page scripting is ever needed. Vision should never be required.

## Verdict

Firefox is a textbook **web-native** citizen: a custom Gecko toolkit that nonetheless publishes one of the richest AX trees on macOS, with 100% bounds coverage, ~89% named interactive elements, readable values/states, universal semantic actions, and — uniquely valuable — stable DOM-id native identifiers on chrome elements. The only real frictions are lazy/truncated deep page subtrees (re-expand on demand) and the multi-process name collision that breaks name-based process targeting. A pure-AX control loop is fully viable here. **Fidelity: 8/10, category: web-native.**
