# TextEdit — Accessibility Tree Analysis

**Bundle:** `com.apple.TextEdit` (`/System/Applications/TextEdit.app`) · **Capture mode:** `activated` · **PID:** 26059

## What the app is built with

TextEdit is a first-party Apple system app built on **AppKit (Cocoa)**. The bundle carries no embedded frameworks and no Electron/Qt/Flutter/Catalyst hints (`frameworks: []`, `hints: []`), which is exactly what a pure-AppKit system binary looks like. The tree shape confirms it: classic NSOpenPanel `AXIdentifier` values (`open-panel`, `OKButton`, `CancelButton`, `NewDocumentButton`, `ColumnView`, `_NS:8`-style autolayout identifiers), an `outline` sidebar, a `browser` (NSBrowser column view), and standard AppKit roles throughout. Zero webareas, zero web content (`surfaces: []`).

## Important capture caveat: this is the Open panel, not the editor

TextEdit was **not running** when capture started (`was_running: false`), so launching it presented the standard **Open file dialog (NSOpenPanel)** rather than a document window. Both captured windows reflect this:

- `w-28178` — "Open" (the open panel, 893×448) — this is what skeleton/full captured
- `w-28185` — "Save Panel Accessory View" (678×64, `visible: false`) — a **ghost window**: an off-screen accessory view AppKit pre-instantiates for the save sheet. It even got picked as `best_window` by the heuristic despite being invisible. CUA agents should filter windows with `visible: false` before choosing a target.

So this analysis rates the file-dialog surface with high confidence; the document-editing surface (an AXTextArea inside a scroll area, which AppKit exposes with full value/selection support) was not captured this run but is a known-good AppKit archetype.

## Tree metrics (full.json, window "Open")

| Metric | Value |
|---|---|
| Total nodes | 129 |
| Named nodes | 73 (57%) |
| Interactive nodes | 69 |
| Interactive named | 42 (61%) |
| Interactive with bounds | 69 / 69 (**100%**) |
| Truncated containers | **0** (`complete: true`) |
| Max depth | 7 |
| Nodes with available_actions | 101 (78%) |
| Value-bearing nodes with value | 22 / 23 (96%) |
| Surfaces (webviews etc.) | none |

Roles histogram: treeitem 30, cell 30, group 23, textfield 21, button 12, scrollarea 3, list 2, menubutton 2, plus window/outline/scrollbar/browser/combobox/handle.

**The unnamed-interactive story is benign.** All 30 treeitems (sidebar locations) are named. The 21 unnamed textfields are NSBrowser/outline **cell textfields whose file/folder names live in `value`** (20/21 carry a value) — identity is fully recoverable, just from `value` instead of `name`. Only 4 buttons and a scrollbar/menubutton are truly unnamed, and those carry `native_id` identifiers to compensate.

**Semantic actions are rich and real:** `Click` (92 nodes), `RightClick` (24), `SetValue` (23), `SetFocus` (15), `Scroll`, `Select`, `Expand`/`Collapse` on menubuttons and the read-only "Where:" combobox. This is a full AXPress-class action surface.

**States are readable:** `disabled` on back/forward and the Open button (correctly disabled with nothing selected), `selected` on the active sidebar row, `expanded`, `readonly`, `offscreen` on scrolled-out rows.

Privacy note: the sidebar outline and browser column contain the user's actual folder/location names in `name`/`value` fields (roughly 60 such nodes); they are deliberately not quoted here.

## What a CUA agent can and cannot do via pure AX

**Can (everything, on this surface):**
- Enumerate sidebar locations by name and `Select` one
- Navigate the column browser: rows are named treeitems / valued cells with `Click`/`RightClick`
- Type into the search field via `SetValue` (native `Search` identifier)
- Press New Document / Show Options / Cancel / Open via `Click` — all with stable `native_id`s (`NewDocumentButton`, `OptionsButton`, `CancelButton`, `OKButton`)
- Read current location from the "Where:" combobox and `Expand` it to change it
- Verify preconditions from states (e.g., Open disabled until a file is selected)

**Cannot / caveats:**
- Nothing material on this window. The only gap is cosmetic: matching browser cells requires searching `value` as well as `name`.
- The document editor itself was not captured this run; expect it to be equally clean (AppKit textarea), but that is inference, not evidence.

## Reach strategy

**Semantic, unconditionally.** Every interactive element has bounds, an action verb, and either a name, a value, or a stable `AXIdentifier`. `native_id`s like `OKButton`/`NewDocumentButton` are ideal durable selectors for compiled routes. No need for keyboard macros, coordinates, CDP (no web content exists), or vision. Keyboard (Cmd-N, Cmd-O, Cmd-Shift-G) is a fine accelerator but never a necessity.

## Quirks

1. **Ghost "Save Panel Accessory View" window** — an invisible 64px-tall pre-instantiated panel that won the `best_window` heuristic; filter `visible: false` windows.
2. **Launch-into-Open-panel behavior** — with no recent document, TextEdit presents NSOpenPanel at launch; a route wanting a blank document should hit `NewDocumentButton` (or Cmd-N) first.
3. **Cell identity in `value`, not `name`** — NSBrowser/outline cell textfields carry their label in `value`; name-only matching misses them.
4. **Duplicate "column view" name** — both the browser and the View Options menubutton are named "column view"; disambiguate via role or `native_id`.
5. Both windows reported `visible: false` / `is_focused: false` at capture time, yet the full tree came back `complete: true` with 100% bounds — no husk behavior.

## Verdict

TextEdit is the AppKit gold standard the fidelity rubric was written against. The captured surface — the standard macOS Open panel — exposes a complete, untruncated, fully-bounded tree with a rich semantic action vocabulary, readable values and states, and stable native identifiers on every commit-path control. The only deductions are the minor name-vs-value split on browser cells and a few unnamed chrome buttons. A CUA agent can run the entire observe→find→act→verify loop here in pure AX with no fallback strategy; the same is expected (though not yet evidenced in this capture) for the document editing window. **Category: native-perfect. Fidelity: 9/10.**
