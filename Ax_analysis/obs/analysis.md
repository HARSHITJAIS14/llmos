# OBS Studio — Accessibility Tree Analysis

**Bundle:** `com.obsproject.obs-studio` · `/Applications/OBS.app` · v32.0.2
**Capture mode:** background (window not focused, on a secondary display region) · pid 26845
**Capture health:** all three captures succeeded (skeleton 16.7 KB, full 20.9 KB, surfaces 98 B), zero errors, `complete: true` on both trees.

## What it's built with

Bundle evidence is unambiguous: **Qt Widgets** (`QtCore/QtGui/QtWidgets/QtSvg/QtXml/QtNetwork.framework`) is the UI toolkit, with **Chromium Embedded Framework** bundled alongside (used only for browser sources/docks and service integration pages, not the main UI), plus Sparkle (updates), Syphon, and the ffmpeg/x264/SRT/RIST media stack. Framework hints: `qt`, `cef`.

The tree shape confirms Qt's accessibility bridge everywhere: `native_id` values are full Qt object paths like `OBSApp.OBSBasic.controlsDock.OBSBasicControls.controlsFrame.streamButton` and `...mixerFrame.mixerToolbar.QToolButton`, and the action vocabulary (`Click`, `Toggle`, `SetValue`, `SetFocus`, `Expand`, `Collapse`, `Select`) is the classic QAccessible mapping. No webarea appears anywhere in the captured window — the CEF runtime is dormant in this tree.

## Measured metrics (full.json, window-scoped)

- **Total nodes:** 62 · **max depth:** 3 (Qt flattens the dock hierarchy aggressively)
- **Named nodes:** 48/62
- **Interactive nodes:** 50, of which **42 named (84%)** — the 8 unnamed are 5 list `row` containers (whose child `statictext` carries the label) and 3 anonymous trailing buttons with no `native_id` (likely dock/titlebar chrome)
- **Bounds:** 62/62 nodes, **100% of interactive nodes** (skeleton variant intentionally omits bounds)
- **Truncated containers:** 0 — no `children_count>0` with missing children
- **Semantic actions:** present on 56/62 nodes (`Click`, `Toggle`, `SetValue`, `Expand/Collapse`, `Select`, `SetFocus`)
- **Values:** 7 nodes carry values — mute checkboxes report `0/1`, the transition-duration incrementor reports `300`, scrollbars report position. Volume sliders are marked `readonly` and expose **no value** — the one real value gap.
- **States:** `disabled` correctly flagged on context-dependent buttons (source Properties/Filters/Remove/Move when nothing is selected); window reports `focused`.
- **Roles histogram:** button 36, row 5, statictext 5, scrollbar 3, checkbox 3, slider 3, menubutton 2, list 2, window 1, group 1, incrementor 1. (Skeleton renders the list leaf texts as `cell` instead of `statictext` — same nodes, different role mapping between passes.)

## What the tree exposes

Essentially the entire OBS control surface, by name and with stable Qt identifiers:

- **Controls dock:** Start Streaming, Start Recording, Start/Configure Virtual Camera, Studio Mode, Settings — all named, bounded, `Click`-actionable.
- **Scenes dock:** a 2-row scene list (one row carries a user-given scene name — described abstractly here), with Add/Remove/Filters/Move Up/Move Down toolbar buttons.
- **Sources dock:** a 3-row source list (audio input, video capture device, display capture) with its full toolbar; disabled states track selection.
- **Audio mixer:** per-channel Properties button, Mute checkbox (with readable 0/1 value and `Toggle` action), and a volume slider per channel — the sliders are the weak spot: `readonly`, no value, no `SetValue`. Channel names appear inside slider/checkbox labels.
- **Transitions dock:** transition menubutton (`Expand/Collapse`), Duration incrementor with readable value and `SetValue`, add/remove/properties buttons.
- **Preview area:** Zoom In/Out buttons, scaling-mode menubutton, X/Y scrollbars with `SetValue` — but the preview canvas itself is a rendered video surface, invisible to AX (as expected).

## What it hides

- **Volume levels:** sliders are readonly with no value — a CUA agent cannot read or set dB via AX; it must open "Advanced Audio Properties" (`AdvAudioProps` button is exposed) where Qt spinboxes will carry values.
- **Preview contents:** pixels only; scene composition must be inferred from the sources list, never the canvas.
- **3 anonymous buttons** with no name and no `native_id` (one accepts `RightClick`).
- **List rows are unnamed containers**; the label lives one level down in a `statictext`/`cell` child with only a `Click` action — selecting a scene/source means clicking the text child or using the list's `Select`.
- The menu bar and status bar are outside this window-scoped capture; a "Script Log" secondary window and a ghost 0x0 invisible window ("OBS Studio", w-28288) exist but were not treed.

## Husk / background behavior

None. Captured fully in the background, unfocused, with `complete: true`, real bounds on every node, and zero truncation. Qt's AX bridge does not collapse when unfocused. `surfaces` is legitimately empty (no web surfaces active).

## Reach strategy for a CUA agent

**Semantic-first, pure AX.** Nearly every workflow closes in-tree: start/stop streaming or recording (`streamButton`/`recordButton` + name flips for verification), toggle mutes (checkbox `Toggle` + value readback), switch scenes (list `Select` / row-text `Click`), add sources/scenes, set transition duration (`SetValue`), open Settings. The Qt `native_id` paths are build-stable and ideal as archetype anchors. Fall back to **keyboard/coordinate** only for: the preview canvas (drag/position sources — coordinate + vision), fine volume control (or route via the AdvAudioProps dialog instead), and the 3 anonymous buttons. CDP is irrelevant unless a browser dock is opened (CEF is bundled but not surfaced here).

## Quirks

- Skeleton vs full role drift: list leaf text is `cell` in skeleton, `statictext` in full.
- Ghost invisible 0x0 window (w-28288) alongside the real main window and a Script Log window.
- Volume sliders advertise `slider` role but behave as readonly meters at the AX layer.
- Qt exposes an unusually flat tree (depth 3 for a heavily docked UI) — everything is a direct child of the window, so structural navigation is by `native_id` path, not tree nesting.
- Disabled-state tracking is live and accurate, making it a free precondition check for agents.

## Verdict

OBS Studio is a **near-model Qt citizen: native-partial, fidelity 8.5/10**. Every primary control is named, bounded, semantically actionable, and stable under background capture with zero truncation — a full observe→act→verify loop is possible in pure AX for streaming, recording, scene/source management, muting, and transitions. It misses native-perfect only on the readonly/valueless volume sliders, a handful of anonymous chrome buttons, unnamed row containers, and the inherently opaque video canvas. Treat it as a semantic-first target with a coordinate/vision fallback reserved solely for canvas manipulation.
