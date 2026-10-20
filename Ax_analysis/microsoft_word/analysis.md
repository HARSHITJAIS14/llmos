# Microsoft Word — Accessibility Tree Analysis

**Bundle:** `com.microsoft.Word` · **Capture mode:** background (app was not running; launched for capture) · **Captured surface:** the DocStage start screen ("Open new and recent files"), not the document editor.

## What the app is built with

Bundle evidence: the Frameworks directory is a wall of Microsoft's shared Office C++ stack — `MsoCF`, `COMBase`, `OLE`/`OLEAutomation`, `MSXML`, `OfficeArt`, `MicrosoftRichEdit`, `Uniscribe`, `Gfx`, plus `CocoaUI.framework` and `FluentUI.framework` as the macOS presentation layer. No Electron, Qt, Flutter, or Catalyst hints. This is the classic cross-platform Office core: custom C++ widgets rendered through Microsoft's own toolkit, with hand-written accessibility providers bridged to macOS AX via a thin Cocoa layer. The tree shape confirms it — the action vocabulary is UIA-flavored (`Click`, `Toggle`, `SetValue`, `SetFocus`, `Expand`/`Collapse`) rather than raw AppKit `AXPress`, and tab strips are exposed as radiobutton groups (a very Office-provider pattern). A couple of nodes carry NSView-style `ax_identifier` values (`_NS:120`, `DocStage`), showing the Cocoa shell underneath.

## What the tree exposes

Real, complete, high-quality tree for the captured window. Metrics from `full.json` (106 nodes, max depth 7, `complete: true`):

- **Bounds: 100%.** Every one of the 106 nodes has pixel bounds — including all 89 interactive-role nodes.
- **Actions: 92/106 nodes** expose semantic actions (`Click` ×83, `SetFocus` ×20, `Toggle` ×8, `SetValue` ×3, plus `Select`, `Scroll`, `ScrollTo`, `Expand`, `Collapse`). This is a fully actionable tree — no coordinate synthesis needed for anything visible.
- **Values and states:** 11 value-bearing nodes; every radiobutton/toggle reports checked state and value; the disclosure reports expanded state; the search textfield accepts `SetValue`. States (`focused`, `checked`, `disabled`) present on 54 nodes.
- **Names: 62/106 overall; 60/89 interactive (67%).** All primary controls are named (Create, Cancel, navigation tabs, filter toggles, the search field, an account menubutton carrying the signed-in user's display name). The recent-documents table exposes 39 cells, 33 of them named with user document titles (described abstractly here for privacy).
- **No truncated containers** in the full capture — every `children_count` is realized.

## What it hides / rough edges

- **8 unnamed buttons**, several of them zero-sized (0×0 or 0-height) scrollbar stepper/ghost parts — harmless clutter, but two or three are real visible buttons (one ~47px wide near the Create/Cancel row) that an agent can only identify by position.
- **13 rows in the recent-files table are unnamed**; identity lives on their child cells instead. An agent must target cells, not rows.
- **Ghost windows:** `windows.json` lists 9 windows for the process; 8 are invisible 29–30 px strips (menu-bar/toolbar phantoms parked off-screen or at y=0), all titled identically. Only `w-28255` is the real focused window. Window-picking heuristics must filter on `visible` + plausible size.
- **`surfaces.json` is empty** — no secondary surfaces (sheets/popovers) at capture time.
- **Only the start screen was captured.** The document editor (ribbon, canvas, formatting panes) is untested here; historically Word's canvas exposes a text area with full content, but ribbon galleries can be heavy. No evidence either way in this capture.
- Regional-English names appear ("Favourites") — string matching should be tolerant of locale variants.

## Husk behavior

None. Background capture (app launched, not foregrounded) produced a complete, named, actionable tree with `complete: true` and zero errors. The Office provider serves AX without requiring focus.

## CUA reach strategy

**Semantic AX is the right and sufficient strategy** for this surface. A pure-AX agent can: switch Home/New/Recent/Open/Shared tabs (`Toggle`), filter Recent/Favourites/Shared-with-me, expand the Templates disclosure, `SetValue` the search field, select a template or recent-document cell (`Click`/`Select`), and press Create/Cancel — the complete new-document and open-recent loops. Keyboard macros are a good secondary (Cmd+N bypasses DocStage entirely; Cmd+O for the open dialog). Coordinates only as fallback for the few unnamed buttons; CDP is inapplicable (no webview); vision unnecessary.

## Verdict

Microsoft Word for Mac is a custom C++/Office-toolkit app that nonetheless ships one of the better third-party accessibility implementations on the platform: 100% bounds coverage, rich UIA-style actions on 87% of nodes, readable toggle states and values, and stable background capture with no truncation and no husk. The gaps are cosmetic — a handful of unnamed buttons, unnamed table rows whose cells carry the names, and a swarm of ghost windows that a window-picker must filter. For the captured start-screen surface a CUA agent can run the full loop in pure AX; the main open question is editor/ribbon fidelity, which this capture did not reach. Category: **native-partial**, at the strong end of that band.
