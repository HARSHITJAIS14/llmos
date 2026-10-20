# Apple Notes — AX Tree Analysis

**Bundle:** `com.apple.Notes` (`/System/Applications/Notes.app`) · **Capture mode:** background (app was launched for the capture, `was_running: false`) · **PID 26055**

## What it's built with

- **AppKit, first-party Apple.** The bundle is a system app with an empty `frameworks` list and no Electron/Qt/Flutter/Catalyst hints in meta.json.
- Tree-shape evidence corroborates: Interface-Builder-style AX identifiers (`_NS:6`, `_NS:46`, `_NS:50`, `_NS:120`) and Notes-internal class-derived identifiers (`ICMNoteListTableView_asList`, `ICMNoteListCell`, `FolderCell`, `Note Body Text View`, `Note Body Scroll View`). The `ICM` prefix is the classic NotesUI/AppKit codebase — this is not Catalyst or SwiftUI-hosted content; it walks like a hand-built NSOutlineView + NSTableView + NSTextView three-pane layout, because it is one.

## Capture quality / metrics (full.json, one window, 1000x660)

- **49 total nodes**, max depth 7, `complete: true`, ref_count 44.
- **28/49 nodes named**; **38 interactive-role nodes**, 24 named directly.
- **100% of interactive nodes have bounds** (38/38).
- **0 truncated containers** in the full tree (`children_count>0` with missing children: none). The skeleton has 4 truncated containers, but that is skeleton-mode's intended pruning, not a defect.
- **Values readable:** the note-body textfield exposes its full text content as `value` (including U+2028 line separators), the sidebar folder-rename textfield exposes its value, the scrollbar exposes `value: "0"` + disabled state, and the Checklist toggle exposes `value: "Off"`. Toolbar buttons carry `disabled` states; tree items carry `expanded`/`selected` states.
- **Semantic actions everywhere:** 37/49 nodes list `available_actions` — `Click`, `RightClick`, `Select`, `SetFocus`, `Scroll`, `Expand`/`Collapse` on menubuttons, and crucially `SetValue` + `TypeText` on the note body editor.
- Roles histogram: 12 button, 9 cell, 6 treeitem, 3 textfield, 3 menubutton, 3 scrollarea, 2 row, 2 statictext, 1 each outline/table/toolbar/dialog/scrollbar, 3 group, 1 unknown (the `FolderCell` wrapper).

## What the tree exposes

The full three-pane app is legible: a **Folders outline** (accounts as expandable tree items — two account sections, each containing folder cells whose descriptions include note counts), a **note-list table** (a date-group header row plus note rows whose cell names are content previews plus a date), and the **note editor** as a single settable/typeable textfield holding the entire note body. The toolbar is fully named (Add Folder, Folders, View Options, New Note, Format, Checklist, Table, Media, Writing Tools, Share, More) with disabled-state signaling for context-dependent buttons. A read-only search field sits at the toolbar's right end (unnamed but identifiable by role/position).

## What it hides / quirks

- **Unnamed interactive nodes are almost all benign:** the three 16x16 window traffic-light buttons, wrapper `treeitem`/`row` nodes whose child `cell` carries the name, the search textfield (disabled/readonly, no name), and the editor textfield (unnamed but carrying the full value and a stable `Note Body Text View` identifier).
- **Window/surface weirdness under background capture:** windows.json reports both windows `visible: false` and `is_focused: false` (app was backgrounded), there is a ghost 500x500 generic window alongside the real one, the root of the real window reports role `dialog` rather than `window`, and surfaces.json types the focused window as `alert`. None of this degrades the tree — the full capture came back complete with bounds. No husk behavior.
- Note body value uses U+2028 line separators instead of `\n`; string matching on note content should normalize these.
- Rich-text structure (headings, checklists, tables inside a note) is flattened into one textfield value; per-paragraph formatting is not visible in this capture.
- `SetValue` on the note body would replace the whole note — prefer `TypeText`/keyboard for appends and careful edits.

## What a CUA agent can do via pure AX

Essentially everything: enumerate accounts/folders with note counts, select a folder (Click on treeitem), pick a note from the list (row names are content previews), read the entire note body from `value`, create a note (New Note button), write content (`TypeText`/`SetValue` on `Note Body Text View`), rename a folder (settable sidebar textfield), open Share/More/Media/View Options menus (Expand). Verification is closed-loop: after typing, re-read the editor's `value`; after creating, watch the note-list table.

**Reach strategy: semantic AX all the way.** No coordinates, no CDP, no vision needed. Keyboard macros (Cmd+N, Cmd+F) are an optional accelerant, not a necessity. The stable `native_id`s (`Note Body Text View`, `ICMNoteListTableView_asList`, `_NS:50` outline) make compiled routes durable.

## Verdict

Apple Notes is a reference-quality AppKit citizen: a small, fully-bounded, action-rich tree with readable values on the exact nodes an agent needs (editor body, list cells, folder outline), zero truncation, and stable identifiers — and it stays fully capturable while backgrounded and unfocused. The only blemishes are cosmetic (unnamed chrome buttons, dialog/alert role oddities on the window root, U+2028 line separators, flattened rich text). Score 9.5/10, **native-perfect**: the full observe-act-verify loop closes in pure AX.
