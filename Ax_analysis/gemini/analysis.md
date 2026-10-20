# Gemini (com.google.GeminiMacOS) — AX Tree Analysis

## What the app is built with

Bundle evidence: the executable is `/Applications/Gemini.app/Contents/MacOS/Gemini` and the only bundled framework signal is `libswiftCompatibilitySpan.dylib` — a Swift runtime compatibility shim. No Electron, Qt, Flutter, or Catalyst hints. This is Google's **native Swift (SwiftUI/AppKit) macOS client**, not a web wrapper.

Tree-shape evidence corroborates this: the window exposes classic native roles — `toolbar`, `sheet`, `outline` > `treeitem` > `cell` (the sidebar list), `scrollarea`, `menubutton`, `heading` — with **no `webarea` anywhere**. Several controls carry real AX identifiers (`sidebar_toggle`, `mic_button`, `stc_button`, `tempChat_button`, `newNotebookRow`, `collapse_button`), which is the signature of a hand-instrumented native UI, not a DOM projection.

## Capture behavior and window quirks

- Capture mode was **`activated`** — the app had to be brought forward to yield a real tree.
- **Ghost windows**: `windows.json` lists 10 windows, *all* `visible: false`, most with degenerate bounds — several 2560×30 strips pinned at (0,0) (menu-bar/overlay panels), a trio of 1280×29 slivers parked off-screen at x=2560, a 500×500 panel, and the one that actually holds the UI, `w-23839`, reported as a tiny 137×187 rect. Window-level geometry from this app is **unreliable**; node-level bounds inside the tree are fine.
- The **skeleton snapshot is a husk**: only ~8 refs — a couple of `children_count>0` groups with no children, two "Temporary chat" buttons, a disabled button, and a `sheet` with a single "Next" button (an onboarding/permission overlay). The full activated snapshot of the same window yields 212 nodes. Background/pre-activation capture of this app cannot be trusted.
- `surfaces.json` is empty (no secondary AX surfaces).
- The full snapshot self-reports `complete: false, truncated: true` (220 nodes observed vs 212 serialized), so a small fringe was clipped, though **zero containers in the serialized tree have `children_count>0` with missing children**.

## What the tree exposes

Measured from `full.json` (python, not eyeballed):

| Metric | Value |
|---|---|
| Total nodes | 212 (max depth 9) |
| Named nodes | 72 |
| Interactive nodes | 134 |
| Interactive named | 69 (51%) |
| Interactive with bounds | 134 (**100%**) |
| Truncated containers | 0 |
| Nodes with `available_actions` | 143 |
| Roles | button 72, treeitem 58, cell 58, group 9, textfield 2, scrollarea 2, heading 2, menubutton 2, plus window/outline/toolbar/sheet/scrollbar/handle/statictext |

- **Sidebar**: an `outline` of 58 `treeitem`>`cell` rows — a list of ~58 conversation entries with personal titles. The treeitems and cells themselves are unnamed, but 55 of them contain a **named `button`** whose name is the conversation title, each with `Click` (and the rows expose `expanded`/`selected`/`focused` states). So the conversation list is fully targetable by name one level down.
- **Chrome**: named toolbar/utility buttons (temporary chat, collapse, sidebar toggle, mic, new-notebook, etc.), two named `menubutton`s, 2 `textfield`s — including the composer, which advertises `SetValue`, `TypeText`, `SetFocus`, `RightClick` and has a name (placeholder) and precise bounds.
- **Semantic actions are rich**: 143 nodes expose `Click` / `RightClick` / `SetFocus` / `SetValue` / `TypeText` — a genuine AXPress-class action surface, plus stable `ax_identifier` native ids on key controls.
- **States** are present and meaningful: `disabled`, `selected`, `expanded`, `focused`, and 108 `offscreen` marks on scrolled-out sidebar rows.

## What the tree hides

- **The chat transcript is essentially invisible.** The main content `scrollarea` carries only a placeholder-like value; the whole tree holds just 1 `statictext` and 2 `headings`. Rendered model responses and prior messages do not appear as readable text nodes. An agent can *send* a message via AX but cannot *read the reply* from this tree.
- **Textfield values are not populated** — the composer exposes SetValue/TypeText but no readable `value`, so verifying typed content requires re-query after focus or another channel.
- 7 unnamed buttons and the 116 unnamed treeitem/cell wrappers dilute the named ratio, though the wrappers are structural.
- The tree flags itself truncated (`complete:false`), so deep corners may be clipped on any given snapshot.

## CUA strategy

- **Semantic AX is the right primary channel for actuation**: every interactive node has bounds, most meaningful controls are named or carry `ax_identifier`s, and `Click`/`TypeText`/`SetValue` actions work. Opening a conversation by title, starting a new/temporary chat, focusing the composer, typing, and clicking send are all pure-AX operations.
- **Reading output needs a fallback**: since the transcript isn't in the tree, pair AX actuation with **vision/OCR (screenshot of the scrollarea)** to read responses, or use clipboard tricks (select-all + copy via keyboard macro) if the app supports them. CDP is not applicable (no web layer).
- **Always capture activated**, target window `w-23839` regardless of its bogus reported bounds, and ignore the nine invisible ghost/overlay windows. Expect a `sheet` overlay (onboarding/permission) to intercept the first interaction — dismiss its single "Next" button if present.
- Use node-level bounds for any coordinate fallback; never trust window-level bounds from this app.

## Verdict

Gemini for macOS is a genuinely native Swift app with a real, action-rich accessibility tree: 100% of interactive nodes have bounds, key controls have names and stable identifiers, and semantic actions (Click/TypeText/SetValue) make the full *input* loop — pick a conversation, compose, send — achievable in pure AX. What keeps it out of the top tier is asymmetry: the app is writable but not readable. The chat transcript is absent from the tree, textfield values aren't surfaced, background capture yields a husk, and the window list is a hall of invisible ghosts with junk geometry. Classified **native-partial, fidelity 7/10** — drive it with semantic AX, verify with vision.
