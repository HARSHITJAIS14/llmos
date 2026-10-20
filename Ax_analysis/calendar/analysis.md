# Calendar (com.apple.iCal) — AX Tree Analysis

## What the app is built with

**Bundle evidence.** System app at `/System/Applications/Calendar.app`, bundle id `com.apple.iCal`. `framework_signals` shows an empty frameworks list and no hints — no Electron, Qt, Flutter, or Catalyst markers. This is first-party Apple **AppKit** (Calendar's classic CalUI stack).

**Tree-shape evidence.** The tree is unmistakably native AppKit: rich `ax_identifier` native ids everywhere (`CALMainWindow`, `MiniCalPrevMonthButton`, `MiniCalNextMonthButton`, `sidebar-mini-month`, `CalendarsControl`, `views-switcher`, `today-button`, `calendar-checkbox-button`, `title-field`, `notes-field`, `date-time-button`), proper semantic roles (grid, outline, treeitem, radiogroup, toolbar, combobox), and no webarea anywhere. No DOM-ish deep nesting — max depth is only 7.

## Capture context

- Capture mode: **background** — the app was launched for the capture (`was_running: false`), window not focused, `visible: false` on every window. Despite that, both skeleton and full captures returned `ok: true` with `complete: true`. **No husk behavior**: the background tree is fully populated with names, values, bounds, and actions.
- 4 windows reported; three are ghost windows with zero-size bounds (0x0), plus the real 935x598 main window (`w-28188`). The capture correctly targeted the real one.
- `surfaces.json` mislabels the main window as `type: "alert"`, and the window root node carries role `dialog` rather than `window` — cosmetic role-mapping quirks, not access problems.

## Metrics (full.json, window-scoped)

| Metric | Value |
|---|---|
| Total nodes | 170 |
| Named nodes | 135 (79%) |
| Interactive nodes | 134 |
| Interactive with name or value | 127 (95%) |
| Interactive with bounds | 134 (100%) — every node in the tree has bounds |
| Truncated containers (children_count>0, children missing) | 0 |
| Value-bearing roles with a value | 24 / 29 |
| Nodes with available_actions | 146 |
| Max depth | 7 |

Roles histogram: button 99, treeitem 12, cell 12, checkbox 9, textfield 7, group 6, statictext 6, radiobutton 6, grid 2, radiogroup 2, plus dialog/scrollarea/outline/scrollbar/handle/list/combobox/toolbar/unknown (1 each).

Actions histogram: Click 140, SetFocus 33, RightClick 16, Toggle 15, SetValue 8, Select 2, Scroll 1, Expand 1, Collapse 1. Semantic actions (AXPress-equivalent Click, plus Toggle and SetValue) are pervasive.

## What the tree exposes

- **Mini-month grid**: a 42-cell grid whose day buttons carry fully descriptive names ("26, Sunday, July" style) — direct semantic date navigation.
- **Navigation chrome**: previous/next month, previous/next day, Today, Add Event, Search textfield, view-switcher radiogroup (Day/Week/Month/Year), calendars toolbar — all named, all Clickable, most with stable `ax_identifier` values, which makes compiled routes robust across sessions and layouts.
- **Sidebar calendar list**: an outline of treeitems/cells with per-calendar checkboxes exposing real state (`Toggle` action, `checked` state, value "1") and editable title textfields (`SetValue` available). The list contains account/calendar entries including a personal email address as a calendar name — readable in full, described here abstractly.
- **Event inspector**: the currently selected event's title, calendar assignment (readonly combobox with value), date button, and notes are exposed as valued nodes.
- **State**: focused/selected/expanded/checked/readonly states are populated; the active view group carries the displayed date as its value.

## What it hides / quirks

- 7 of 134 interactive nodes are unnamed — all are chrome artifacts: sidebar splitter/disclosure buttons (several with zero-height bounds) and three tiny 16x16 window traffic-light-adjacent buttons. None matter for task automation.
- Sidebar calendar textfields have `name` set to the account provider label while the actual calendar title lives in `value` — an agent matching on name alone would see duplicates; match on value or `native_id` (which embeds the calendar title).
- Multiple sidebar cells simultaneously report a `focused` state — the focus flag is unreliable at the cell level; use `selected` instead.
- Skeleton view prunes large containers by design (the 42-child grid, radiogroups show `children_count` only), but the full capture expands everything: zero truncated containers.
- One `unknown`-role node (`sidebar-mini-month`) and the dialog/alert role mislabels noted above.
- Three zero-size ghost windows in the window list; ignore anything with 0x0 bounds.

## What a CUA agent can / cannot do via pure AX

**Can:** navigate to any date (mini-month day buttons or prev/next/Today), switch views, toggle calendar visibility (real Toggle + checked state readback), create an event (Add Event button), read the selected event's title/calendar/date/notes, rename calendars via SetValue, search via the Search textfield, and verify every action by re-reading values and states. Bounds are present on 100% of nodes, so coordinate fallback is always available but should rarely be needed.

**Cannot / caveats:** the day-view event canvas itself (individual event blocks on the timeline) is not in this capture's day area beyond the selected event's inspector fields — event blocks may need a fresh snapshot after navigation; the event-editing popover appears as a separate surface after Add Event and must be re-snapshotted. Nothing structural blocks any of this.

## Reach strategy

**Semantic-first, and it fully suffices.** Stable `ax_identifier` native ids make this an ideal target for compiled routes (target `today-button`, `views-switcher`, `calendar-checkbox-button`, `MiniCalNextMonthButton` by id). Keyboard macros (Cmd-T today, Cmd-1..4 view switch, Cmd-N new event) are a fine accelerator but not required. Coordinates and vision are unnecessary; CDP is inapplicable (no web content).

## Verdict

Apple Calendar is a near-perfect native AX citizen: a compact 170-node AppKit tree with 100% bounds coverage, 95% of interactive elements named or valued, real Toggle/SetValue/Click semantics, readable checkbox and textfield state, zero truncation, and — notably — full fidelity under **background** capture with the window invisible. The only blemishes are a handful of unnamed chrome buttons, a name-vs-value mismatch on sidebar calendar textfields, an unreliable per-cell `focused` flag, and cosmetic role mislabels (window-as-dialog, surface-as-alert). A pure-AX cognitive loop (observe → act → verify) closes completely here. **Category: native-perfect. Fidelity: 9/10.**
