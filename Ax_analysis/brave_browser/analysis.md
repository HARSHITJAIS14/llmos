# Brave Browser — Accessibility Tree Analysis

**Bundle:** `com.brave.Browser` · `/Applications/Brave Browser.app`
**Capture mode:** `activated` (app was not running; the capture launched it, pid 25785)
**Framework evidence:** the bundle ships a single monolithic `Brave Browser Framework.framework` — the classic Chromium-fork layout (identical to Chrome's "Google Chrome Framework"). No Electron/Qt/Flutter/Catalyst hints. Tree shape confirms it: Views-toolkit chrome (toolbars, `ax_dom_identifier` native ids like `view_1001`, tabs modeled as `radiobutton` inside a `tablist`) wrapping a Blink `webarea` for page content.

## What was captured

- **windows.json:** 12 windows, of which ~9 are ghost/utility windows — invisible 29–30 px-tall strips at (0,0) or (2560,536) and a 1x1 px window, all titled just "Brave Browser". Only one real window ("New tab") is visible. Any window-enumeration strategy must filter `visible && height > 100` or it will target husks.
- **skeleton.json (822 B):** a husk — one window containing 4 nodes with actions but almost no names (three anonymous buttons = the traffic-light window controls, plus a truncated group with `children_count: 1`). This is Chromium's dormant AX state: until the renderer's accessibility mode is switched on by an AT query, the tree is empty scaffolding. The full snapshot, taken after activation, is 14x larger. Background/pre-activation capture is therefore NOT stable here.
- **full.json (44 KB, `complete: true`):** 56 nodes, max depth 10, one focused window at 1036x802.
- **surfaces.json:** empty surface list (no sheets/popovers open).

## Metrics (computed from full.json)

| Metric | Value |
|---|---|
| Total nodes | 56 |
| Named nodes | 28 (50%) |
| Interactive nodes (button/textfield/combobox/link/radiobutton/…) | 24 |
| Interactive named | 21 (87.5% — the 3 unnamed are the window traffic-light buttons) |
| Interactive with bounds | 24/24 (100%) |
| Truncated containers (children_count>0, children absent) | 2 |
| Nodes carrying `available_actions` | 52 (93%) |
| Roles histogram | group 23, button 13, combobox 8, toolbar 3, and 1 each of window/webarea/main/tablist/radiobutton/textfield/statictext/link/image |

## What the tree exposes

The **browser chrome is excellent**: Back/Forward/Reload/Bookmark buttons named with `disabled` states; the address bar is a named `textfield` ("Address and search bar") with `focused` state and a rich action set (`Click, RightClick, SetValue, SetFocus, TypeText`); Brave's extension-style buttons (Shields, Rewards, Wallet, VPN, Leo AI, Extensions, Tab search) are named `combobox` nodes with `Expand/Collapse/Select/SetValue/TypeText`; the tab strip is a `tablist` of `radiobutton` tabs carrying `checked/selected` states, a `value`, a per-tab Close button, and even memory usage in the accessible name. Native ids (`ax_dom_identifier: view_NNNN`) are stable Views ids useful for re-identification across snapshots.

Semantic actions are first-class throughout — well beyond bare AXPress: Click, RightClick, SetValue, TypeText, Toggle, Select, Expand, Collapse, ScrollTo, SetFocus.

## What the tree hides

The **web content is only partially materialized**. The `webarea` ("New Tab") is present and focused, and its top-level DOM groups appear with bounds, but the page's `main` region reports `children_count: 10` with no children serialized, and an offscreen group reports `children_count: 5` unexpanded — Chromium lazily populates web-content AX and deep serialization stopped at those containers. On this new-tab page that costs little; on a real site it means the full DOM would need on-demand expansion of the webarea subtree (which Chromium does support once AX is engaged). Values are thin: the address-bar textfield exposes no `value` attribute in this capture (the field was empty), while statictext and the tab radiobutton do carry values — value readability is plausible but unproven for filled fields.

## What a CUA agent can / cannot do via pure AX

**Can:** drive all browser chrome semantically — focus the address bar, `SetValue`/`TypeText` a URL, click Reload/Back, open/close/switch tabs (radiobutton toggle + Close button), invoke Shields/Wallet/VPN popups via Expand, right-click for context menus. All targets have exact bounds as coordinate fallback.

**Cannot (from this snapshot alone):** enumerate deep page content without expanding the truncated `main`/group containers; verify readback of a filled address bar value; capture anything useful before the app is activated (the skeleton husk); pick the right window without filtering out the 9 ghost windows.

## Reach strategy

1. **Semantic AX first** for chrome and shallow page content — names, states, and rich actions make this the primary loop.
2. **On-demand subtree expansion** of the `webarea` for page interaction; if the harness cannot expand lazily-populated containers, fall back to **CDP** (Brave honors `--remote-debugging-port`), the highest-fidelity channel for in-page work.
3. **Keyboard macros** (Cmd+L, Cmd+T, Cmd+W) as robust shortcuts for chrome actions.
4. Coordinates/vision only as last resort; bounds coverage is 100% so blind vision is unnecessary.

## Quirks

- **Ghost windows:** 9+ invisible utility windows (29–30 px strips, a 1x1 px window) that must be filtered.
- **Husk on background/pre-activation:** skeleton captured before Chromium's AX engagement is a 4-node shell with unnamed buttons; the tree only becomes real after activation and an AT query.
- **Tabs as radiobuttons**, not AXTab — match on `tablist > radiobutton` with `selected` state.
- **Extension/feature buttons as comboboxes** (Expand/Collapse), not buttons.
- **Lazy webarea:** `children_count` present but children unserialized on `main` and offscreen groups.
- Best-window bounds in meta (129x146) disagree with the actual window (1036x802) — window metadata was captured mid-launch.

## Verdict

Brave is a Chromium fork and behaves exactly like one: a first-rate Views-based chrome tree with named, bounded, richly-actionable controls, wrapping a Blink webarea that exposes real DOM semantics but only once accessibility is engaged and only as deep as the serializer walks. Classified **web-native, fidelity 7/10**: it loses points for the two truncated web-content containers, the unproven value readback on filled textfields, and the pre-activation husk. For a CUA agent this is a strong pure-AX target for all browser-level tasks; for dense in-page work, expand the webarea on demand or step up to CDP, and always activate the app and filter ghost windows before trusting a snapshot.
