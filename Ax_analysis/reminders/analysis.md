# Reminders — AX Tree Analysis

## What the app is built with

**Bundle evidence:** `com.apple.reminders` at `/System/Applications/Reminders.app` — a first-party Apple system app. `framework_signals.frameworks` is empty (system apps link OS frameworks directly, nothing bundled) and there are no Electron/Qt/Flutter/Catalyst hints. Reminders is a SwiftUI-heavy app hosted in an AppKit shell, and the tree shape confirms this.

**Tree-shape evidence:** classic Apple accessibility topology — `outline > treeitem > cell` for both the sidebar and the reminder list, `_NS:*` ax_identifiers on containers (NSView-backed), a proper `toolbar` with named `button`s, and SwiftUI tells: `layoutitem` nodes, `unknown` role wrappers inside sidebar cells, and `group`-wrapped `switch + textfield` pairs for each reminder row. This is a genuine native AX tree, not a webarea.

## Capture context

- Capture mode: **background** — the window reports `visible: false, is_focused: false`, yet the full tree came back intact (88 nodes, no empty husks). No husk-on-background behavior.
- One window (768x692). Skeleton reports `complete: true`; the full capture reports `complete: false` with `ref_count: 78` vs 88 emitted nodes — a soft incompleteness flag, but **zero** containers have `children_count > 0` with missing children, so nothing observable was truncated.

## Metrics (computed from full.json)

| Metric | Value |
|---|---|
| Total nodes | 88 |
| Named nodes | 51 (58%) |
| Max depth | 9 |
| Interactive nodes (button/textfield/cell/switch/outline/menubutton...) | 54 |
| Interactive named | 39 (72%) |
| Interactive with bounds | 54/54 (**100%**) — in fact all 88 nodes have bounds |
| Truncated containers | 0 |
| Nodes exposing available_actions | 65 (Click on 50; also Toggle, SetValue, SetFocus, Select, Scroll, RightClick) |
| Value-bearing nodes | 13 (6 textfields, 5 switches, 2 statictexts) — values present |
| Roles histogram | button 23, cell 15, treeitem 14, group 9, textfield 8, switch 5, unknown 3, outline 2, scrollarea 2, statictext 2, grid 1, toolbar 1, dialog 1, menubutton 1, layoutitem 1 |

## What the tree exposes

- **Sidebar:** a named "Account Lists" `outline` containing tree items for smart lists (a grid of six named smart-list buttons) and user lists (cells named with list titles and reminder counts, plus per-cell buttons).
- **Main list:** an `outline` of ~5-6 reminder rows. Each row is a `group` containing a **named `switch` with a value** (the completion checkbox — Toggle action exposed) and a **`textfield` with a value and `SetValue`** (the reminder title, editable in place). This is the full read/write loop for a reminder in pure AX.
- **Toolbar:** five named, Clickable buttons — Add List, Sidebar, Share List, Add Section, Add Reminder — plus a search textfield (unnamed, but SetValue-capable, with a named clear button inside).
- **Live summary:** a readonly textfield announcing the current list name and reminder count — useful as a cheap verification anchor after mutations.
- **Semantic actions everywhere:** Click, Toggle, SetValue, SetFocus, Select, Scroll, RightClick. This is as action-rich as macOS AX gets.

## What it hides / gaps

- **15 unnamed interactive nodes:** the 6 reminder-title textfields (compensated by their `value`), 4 cells, 4 buttons (three of which are the bare window-chrome buttons at dialog level — close/minimize/zoom), and one outline (the reminders outline itself lacks a name; only the sidebar outline is named).
- The `unknown` role wrappers in sidebar cells (SwiftUI internals) add noise but don't block anything.
- `complete: false` on the full capture suggests a few refs weren't fully resolved; nothing user-facing appears missing.

## Quirks

- The window root reports role **`dialog`** (not `window`), and surfaces.json lists the focused window with type **`alert`** — likely an artifact of the SwiftUI window hosting; don't filter surfaces by type here or you'll drop the main window.
- The summary textfield name uses an odd comma-spaced pattern ("<list> , N reminders").
- Reminder rows are found by **value, not name** — a finder that only matches `name` will miss every reminder title.
- Window was invisible and unfocused at capture time yet yielded a complete, bounded tree: excellent background-capture stability.

## What a CUA agent can / cannot do via pure AX

**Can:** enumerate lists and reminders (reading titles from textfield values), mark reminders complete/incomplete (`Toggle` on the switch), rename a reminder (`SetValue` on its textfield), create a reminder (Click "Add Reminder", then SetValue on the newly focused textfield), create lists/sections, search (SetValue on the toolbar search field), open context menus (RightClick), and verify outcomes via the live count textfield and switch values. All targets have exact bounds as a coordinate fallback.

**Cannot / harder:** detail-level editing (date, priority, notes) is behind the info popover, which is not in this capture and needs a follow-up snapshot after opening it; drag-to-reorder is not expressible in AX actions.

**Reach strategy:** **semantic AX is the primary and sufficient strategy** — find by role+value/name, act with Click/Toggle/SetValue, verify with values and the count textfield. Keyboard macros (Cmd+N for new reminder) are a fine accelerator; coordinates are a solid fallback since bounds coverage is 100%. CDP and vision are unnecessary.

## Verdict

Reminders is a near-ideal AX citizen: a fully native Apple SwiftUI/AppKit tree with 100% bounds coverage, readable values on every value-bearing control, rich semantic actions including SetValue and Toggle, zero truncated containers, and full fidelity even when captured in the background. The only deductions are cosmetic naming gaps (reminder titles live in `value` rather than `name`, a handful of unnamed chrome buttons/cells) and the odd `dialog`/`alert` role reporting on the window. A CUA agent can run the complete observe-act-verify loop here in pure AX with no fallback tier required. Score: 9/10, category native-perfect.
