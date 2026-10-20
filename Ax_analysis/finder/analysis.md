# Finder — Accessibility Tree Analysis

**Bundle:** `com.apple.finder` · `/System/Library/CoreServices/Finder.app`
**Capture mode:** `activated` (the app had to be brought forward to get a real tree)
**Analyzed window:** the frontmost browser window ("Recents" view, column layout)

## What it's built with

Pure **AppKit**. The bundle is a first-party system app with an empty
`frameworks` list and no Electron/Qt/Flutter/Catalyst hints. The tree confirms
it: `native_id` values are NSView-style AX identifiers (`_NS:8`, `_NS:61`,
`_NS:70`), the window carries the identifier `FinderWindow`, the content view is
`ColumnView`, and the role vocabulary is classic AppKit — `browser`, `outline`,
`scrollarea`, `toolbar`, `treeitem`. This is the reference implementation of
macOS accessibility, and it mostly reads like it.

## Metrics (computed from full.json)

| Metric | Value |
|---|---|
| Total nodes in window-scoped tree | 1,571 (server observed 2,374 before truncation) |
| Max depth | 7 |
| Named nodes | 58 |
| Interactive nodes | 787 |
| Interactive nodes with a `name` | 30 (3.8%) |
| Interactive nodes with bounds | 787 (100%) |
| Value-bearing nodes with `value` | 752 / 752 (100%) |
| Nodes exposing semantic actions | 814 (Click 807, RightClick 754, SetValue 753, SetFocus, Scroll, Select) |
| Truncated containers (children_count>0, children missing) | 0 in the serialized tree, but 6 nodes flagged `subtree_truncated` and the capture reports `complete: false, truncated: true` |
| Roles histogram | group 753, textfield 751, treeitem 27, cell 27, button 5, scrollarea 2, plus window/outline/scrollbar/browser/list/handle |

## What the tree exposes

- **Sidebar:** an `outline` named "sidebar" containing 27 `treeitem` rows, every
  one named, each wrapping a named `cell`, with Click actions and
  selected/expanded states. Fully drivable semantically.
- **Toolbar:** every control is named and actionable — Back/Forward group, a
  view-mode `combobox` whose value reads the current mode ("as Columns"),
  "Group" and "Action" menubuttons with Expand/Collapse, "Share" and
  "Edit Tags" buttons (correctly reporting `disabled` when no selection), and a
  "Search" textfield with Click/SetFocus.
- **File listing:** the dominant pattern is ~750 `group` → `textfield` pairs —
  the item-name cells of the Recents list. Each textfield carries the item's
  name as its `value` (a large list of personal file names; not quoted here),
  100% have bounds, and each offers Click / RightClick / SetValue. SetValue on
  these is the rename affordance.
- **States are honest:** `offscreen` (1,507 nodes — most of the huge list is
  scrolled out of view), `disabled`, `selected`, `expanded` all appear.

## What the tree hides / quirks

1. **Truncation on big listings.** The capture reports `complete: false`; the
   `browser → scrollarea → list` chain is flagged `subtree_truncated`. A Recents
   view over a large home directory simply overflows any node budget. Agents
   must scope queries (find by name/role) rather than pull the whole tree, and
   must scroll + re-snapshot to reach offscreen items.
2. **Unnamed interactive nodes are the norm in the listing.** Only 30/787
   interactive nodes have a `name` — but this is misleading rather than fatal:
   the file-cell textfields carry their identity in `value`, not `name`. Window
   chrome buttons (close/minimize/zoom) are also unnamed in the skeleton
   (identifiable only by role+position; one Eject button has a description).
3. **Ghost windows.** `windows.json` lists 9 windows, all titled just "Finder",
   all `visible: false`: several 2560×30 strips at the top of the screen
   (desktop/menu-bar-adjacent proxy windows), 1280×29 slivers parked on a
   second display, and a 64×64 square (a drag/icon proxy). The real "Recents"
   window (w-28194) is not among them — the window enumerator's "best_window"
   pick was a ghost. Window discovery for Finder cannot trust title or the
   window list alone.
4. **Odd `focused` fan-out:** 779 nodes report `focused`, clearly a propagation
   artifact of the focused list; don't use `focused` as a uniqueness key here.
5. **Activation required.** Capture mode was `activated`; combined with the
   ghost-window inventory, a background snapshot of Finder is unreliable — not
   an Electron-style webarea husk, but not clean background capture either.
6. `surfaces.json` is empty — no secondary surfaces (sheets/popovers) at
   capture time.

## What a CUA agent can and cannot do via pure AX

**Can:** navigate the sidebar by name; switch view modes via the combobox; open
the Action/Group menus; invoke toolbar buttons; focus and type into Search;
click, right-click (context menu), select, and rename (SetValue) any file row
that is materialized in the tree; read selection and disabled states; read
every visible item's name from textfield values; everything has accurate
bounds as a coordinate fallback.

**Cannot (without extra steps):** enumerate a very large folder in one
snapshot (truncation); reliably find the working window from the window list
(ghosts); identify window-chrome buttons by name; operate while fully in the
background.

## Reach strategy

**Semantic-first.** Drive the sidebar, toolbar, and file cells through AX
actions (Click/RightClick/SetValue), using role+value queries for file rows
since names are absent. Layer **keyboard macros** for what Finder does best
that way: Cmd+Shift+G (Go to Folder) beats scrolling a truncated list every
time, Cmd+1/2/3/4 for view modes, Enter to rename, Cmd+O to open, arrow keys
for selection. Use **scroll + incremental re-snapshot** for long listings.
Coordinates are a safe fallback (100% bounds coverage). CDP is irrelevant;
vision is unnecessary.

## Verdict

Finder is a genuine, richly actionable AppKit tree — 100% bounds, 100% values
on value-bearing roles, real semantic actions including SetValue-rename and
RightClick context menus, and honest state reporting — but it is not
"native-perfect" in practice. Large listings truncate, the file rows identify
themselves through `value` rather than `name`, the window list is polluted
with invisible ghost windows that hide the real one, and capture required
activation. A CUA agent gets a full read-act-verify loop here as long as it
scopes its queries, uses Go-to-Folder-style keyboard shortcuts instead of
brute-force enumeration, and resolves windows by content rather than title.
**Category: native-partial. Fidelity: 7/10.**
