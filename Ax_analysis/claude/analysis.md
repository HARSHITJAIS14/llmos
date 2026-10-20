# Claude Desktop (com.anthropic.claudefordesktop) — AX Tree Analysis

## What it is built with

Bundle evidence is unambiguous: `Electron Framework.framework`, four Chromium helper apps
(`Claude Helper (GPU/Plugin/Renderer).app`), plus `Squirrel.framework` (Electron auto-updater),
`Mantle` and `ReactiveObjC`. The capture tool's own hint list says `electron`. Tree-shape
evidence agrees: the window body is a deep stack of anonymous `group` nodes (13 of 19 nodes)
terminating in two `webarea` nodes — the classic Chromium-renderer AX bridge shape. There is
no AppKit chrome beyond the window itself and three 16x16 buttons at the top-left, which are
the macOS traffic-light close/minimize/zoom controls (Electron draws everything else itself).

Capture context: the app was **not running** before capture (`was_running: false`); it was
launched and captured in `activated` mode. The visible window was the freshly opened 600x600
sign-in window (one webarea carries the app's sign-in page title) — no user content was on
screen, and none appears anywhere in the tree.

## Metrics (computed from full.json)

- Total nodes: **19**; max depth: **10**
- Roles: group x13, button x3, webarea x2, window x1
- Named nodes: 3 (the window, one wrapper group, one webarea page title)
- Interactive nodes: **3 buttons — all unnamed** (0% named); all 3 have bounds (100%),
  but they are the 16x16 window traffic lights, not app functionality
- Values on value-bearing roles: **none** (no textfields, toggles, or values anywhere)
- Truncated containers: **2** — both webareas bottom out in a `group` with DOM identifier
  `root` (and a portal container) that reports `children_count: 1` but delivers **no children**
- Actions exposed: Click, RightClick, ScrollTo, SetFocus — generic, on husk nodes only
- Skeleton capture: 750 bytes, same husk (window + 3 unnamed buttons + collapsed group chain)
- Surfaces: empty list

## What the tree exposes vs hides

Exposed: the window frame, its bounds, focus state, the three window-management buttons,
and two webarea shells (one 600x600, one collapsed to ~1px height) whose React roots are
visible as DOM-identifier groups (`root`, `portal-root`, a React `_r_` id) — proof the
Chromium AX bridge is *partially* awake — but the entire DOM below the root div is withheld.
Hidden: everything that matters. The sign-in form, text inputs, buttons, links, the eventual
chat UI — none of it materializes even with the app activated and focused. The renderer never
hydrated its accessibility tree for this capture (Chromium enables full AX lazily; Electron
apps frequently need an assistive-client poke or the `AXManualAccessibility` attribute set on
the app before the DOM is published).

## Ghost windows

Window listing shows **9 windows** for the pid, of which 8 are invisible husks: four 2560x30
strips pinned at the top of the display and four 1280x29 strips parked off-screen — Electron
menu-bar/overlay artifacts. Only `w-28298` (600x600, focused, visible) is real. A naive window
enumerator would target the wrong surface 8 times out of 9.

## What a CUA agent can do here via pure AX

- Can: find the window, read its bounds, close/minimize/zoom it (unnamed but positionally
  identifiable traffic lights), focus the webarea, right-click/scroll the husk.
- Cannot: see or press any in-app control, read or set any text, enumerate conversations,
  verify any action's effect. The full loop (locate -> act -> verify) is impossible in AX
  as captured.

## Reach strategy

1. **First retry AX after forcing accessibility on**: set `AXManualAccessibility = true`
   (or `AXEnhancedUserInterface`) on the app element and re-snapshot — Electron/Chromium
   often publishes the full DOM-backed tree after this, which would re-grade the app as
   web-native. This is the highest-value next probe before writing the app off.
2. If that fails: **keyboard macros** (Tab traversal, Enter, app shortcuts) fired at the
   focused webarea — Electron routes keys correctly even when AX is a husk.
3. **Vision + coordinate clicking** as the general fallback; the window bounds are reliable.
4. **CDP** only if the app is launched with a remote-debugging port (not available by default).

## Quirks

- Husk persists even in `activated` capture mode — activation alone did not wake Chromium AX,
  so background capture would certainly be a husk too.
- Webarea reports `complete: true` and `focused` while delivering an empty DOM: the capture
  is "successful" by envelope but semantically empty. Do not trust `ok: true` here.
- React internals leak as `ax_dom_identifier` values (`root`, `portal-root`, `_r_0_`) —
  useful anchors for detecting whether hydration ever happens.
- One webarea is squashed to ~1px height at the window top; the other overlays the full
  window — duplicate-renderer layering typical of Electron pre-auth screens.
- 8:1 ghost-to-real window ratio.

## Verdict

Claude Desktop is a textbook **electron-veil**: bundle and tree both scream Electron, and the
accessibility tree delivered is a webarea husk — 19 nodes, zero named interactive elements,
zero values, two containers that admit to children they refuse to produce. The only genuinely
actionable AX elements are the three OS-drawn window buttons. Fidelity 2/10 (bounds are present
on everything shown and generic Click actions exist, but nothing app-functional is reachable).
A pure-AX agent cannot operate this app as captured; the immediate remediation is the
`AXManualAccessibility` poke and re-snapshot, with keyboard-macro and vision/coordinate
fallbacks otherwise. Treat any window enumeration for this pid with a visibility filter.
