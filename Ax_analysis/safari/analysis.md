# Safari — AX Tree Analysis

**Bundle:** `com.apple.Safari`, system app at `/System/Volumes/Preboot/Cryptexes/App/System/Applications/Safari.app` (cryptex-mounted, as all modern system Safari builds are).
**Framework signals:** empty `frameworks` / `hints` lists — no Electron, Qt, Flutter, or Catalyst markers. This is first-party AppKit (with WebKit for page content).
**Capture mode:** `background`, app already running (pid 22839). No capture errors.

## What was captured

- **12 windows** enumerated, of which 11 are invisible artifacts: several 29–30px-tall strips spanning the full screen width (Safari's ghost/hosting windows — toolbar layer hosts, tab-bar strips, and similar NSWindow shells), one 500x500 hidden window, and one 803px-tall hidden window. Only one window is visible: **"Start Page"**, reported by the window server with tiny bounds (108x151) — likely a minimized-thumbnail/occluded report — while the AX tree itself reports the real window frame (1087x803 at x=2753). Ghost-window noise is a real quirk: a CUA agent must filter to the visible, titled window.
- **surfaces.json:** empty surfaces list — no separately addressable web surfaces registered at capture time.
- **skeleton.json:** clean top-level chrome — toolbar (sidebar button, tab-group picker, back/forward segmented control, smart search field with `SetValue`, downloads, share, new tab, tab overview) plus a tab bar exposed as radiobuttons with `isActive` encoded in the AX identifier. Rich, stable `ax_identifier` native IDs throughout (e.g. `WEB_BROWSER_ADDRESS_AND_SEARCH_FIELD`, `NewTabButton`, `TabBarTab?isPinned=...&isActive=...`).
- **full.json:** window-scoped tree, 157 nodes, max depth 8, `complete: false` flagged by the capturer (ref budget: 145 refs issued), yet **zero truncated containers** — every node with children has them inlined.

## Metrics (computed from full.json)

| Metric | Value |
|---|---|
| Total nodes | 157 |
| Named nodes | 132 (84%) |
| Interactive nodes (button/link/textfield/radiobutton/switch/menubutton) | 135 |
| Interactive named | 128 (95%) — 7 unnamed glyph-only buttons |
| Interactive with bounds | 135 (100%) |
| Truncated containers | 0 |
| Max depth | 8 |
| Roles | button 121, group 9, link 8, list 6, switch 2, radiobutton 2, plus window/tablist/toolbar/scrollarea/scrollbar/textfield/menubutton/handle/unknown |
| Actions exposed | Click, RightClick, SetFocus, SetValue, Toggle, Select, ScrollTo, Scroll, Expand, Collapse |
| Value-bearing roles with value | 4/5 (switches report 0/1, tab radiobuttons report true/false; the smart search field carried no value attribute in this capture) |

## What the tree exposes

The captured window is Safari's **Start Page**, which is fully native AppKit — there is **no webarea node anywhere in this tree**. The content region is a scrollarea containing six lists of named buttons (a favorites row of ~12 items, a frequently-visited-style grid of ~30, a suggestion list of ~42, plus smaller lists) — these buttons carry personal browsing-history and bookmark titles, all named and all bounded. Chrome is exemplary: every toolbar control has a semantic `ax_identifier`, the address bar accepts `SetValue`, tabs are toggleable radiobuttons whose identifier string encodes pinned/active state, and the second (inactive) tab's page title is readable from the tab button itself.

## What it hides / quirks

- **Background-capture state noise:** all 157 nodes carry `offscreen`, and 98 carry `disabled` (91 of the 121 buttons) — artifacts of the window being unfocused/occluded on another display at capture time, not real disablement. An agent must not filter on these states for a backgrounded Safari window, or it will conclude nothing is clickable.
- **Ghost windows:** ~11 invisible NSWindow shells per the window list; window-picker logic must prefer `visible && title != "Safari"`.
- **No web content in this capture:** with the Start Page active, WebKit's AXWebArea never appears. When a real page is frontmost, Safari is the canonical web-native browser — WebKit projects the full DOM into AX — but that claim comes from the platform, not this JSON; this capture only proves the native chrome side.
- `complete: false` with a ref-count cap (145) suggests the capturer's ref budget ran out, though no container was actually left truncated.
- 7 unnamed icon buttons (window-edge/overlay controls) would need coordinates or descriptions to disambiguate.

## What a CUA agent can do via pure AX

Everything in the browser chrome: focus the address bar and `SetValue` a URL, press New Tab / Tab Overview / Downloads / sidebar, switch tabs via `Toggle` on the tab radiobuttons (active tab is machine-readable), right-click tabs for context menus, and click any Start Page item by name. Web-page interaction was not exercised here, but Safari's WebKit AX bridge normally exposes it fully once a page is loaded and the window is frontmost.

## Reach strategy

**Semantic-first.** Target by `ax_identifier` (stable, descriptive, parameter-encoded) with name fallback; use `SetValue` on the smart search field plus keyboard (Cmd+L, Cmd+T) as a robust macro layer. Coordinates are available (100% bounds) as a tertiary fallback. No CDP needed — this is not Chromium; vision is unnecessary except for the 7 unnamed glyph buttons.

## Verdict

Safari presents one of the highest-fidelity native trees on the platform: complete, deeply named, fully bounded, action-rich, with first-class stable identifiers, and it yields all of this even under background capture — no husk behavior at all. Its deductions are noise rather than absence: spurious `offscreen`/`disabled` states when unfocused, a swarm of ghost windows to filter, a handful of unnamed glyph buttons, and an address field that did not report its value in this pass. Classified **native-partial** only because this capture shows the native chrome/Start Page with minor gaps and no web content was on screen to confirm the DOM bridge; for chrome-level driving it is effectively native-perfect. Score: **8.5/10**.
