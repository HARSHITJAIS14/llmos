# LLM OS: Core Learnings & Automation Guidelines

This document synthesizes our core discoveries, architectural decisions, and automation strategies derived from our daily experiments (e.g., Day 1, Day 2).

---

## 1. Workspace & Workflow Organization

To keep the project organized and prevent chaos as complexity grows, we follow a strict directory convention:

- **`experiments/`**: All scratch scripts, JSON dumps, failed attempts, and WIP code. **Every new feature or test must start here in its own named subfolder.**
- **`tasks/`**: Verified, working, fully documented scripts for specific automation tasks. Only successful experiments are promoted here.
- **`dayX/`**: Daily research notes and reports.

**Rule:** Never leave scratch scripts or JSON dumps in the root directory.

---

## 2. macOS GUI Automation: The Three App Archetypes

We classify applications into three tiers, each requiring a completely different automation strategy.

### A. Native / Catalyst Apps (Finder, WhatsApp, Safari, Calendar)
- **Characteristics:** Native accessibility integration.
- **Strategy:** A single `agent-desktop snapshot` command captures the entire accessibility (AX) tree. No DFS or drill-downs are needed.
- **Quirks:** Catalyst apps (like WhatsApp) do not always appear in `list-windows --app`. Apps with multiple helper extensions (like Calendar) can cause window inventory timeouts; scope snapshots directly using `--surface popover` or `--surface focused` to inspect popover UI elements (`QuickEventNewEventButton`, `QuickEventCell`).

### B. Electron / React Desktop Apps (Notion, VSCode)
- **Characteristics:** Hostile to the Accessibility API. They truncate their internal DOM behind generic webareas (e.g., `notion-app`) to save memory.
- **Strategy (The DFS Drill-Down):** 
  - Find the root web container.
  - Recursively check for nodes with `children_count > 0` but no actual `children` array.
  - Run `snapshot --root <ref_id>` to force Chromium to serialize and expose the hidden DOM.
  - Reconstruct the full tree in-memory.
- **Quirks:** Semantic clicks (`AXPress`) are often silently swallowed by React routing. You must use physical coordinate clicks (`mouse-click --xy`). Ghost windows often cause `AMBIGUOUS_TARGET` errors; you must explicitly filter for `visible: true` and `is_focused: true`.

### C. Browser Web Apps (YT Music via Safari)
- **Characteristics:** Browsers natively expose their DOM to the AX tree. 
- **Strategy:** Open the URL directly via CLI. The tree is native and requires only one snapshot. Search for buttons/links by name and click via coordinate.

### D. Structurally Transparent, Spatially Opaque Apps (OBS Studio, Qt)
- **Characteristics:** Exposes the full hierarchical UI to the Accessibility Tree, but intentionally refuses to serialize screen coordinates (`bounds: None`).
- **Strategy:** Physical `mouse-click` is impossible because the OS doesn't know where the button is. You must query the ephemeral `ref_id` and dispatch a synthetic `AXPress` (`agent-desktop click <ref_id>`). The OS will route the click in memory.

---

## 3. The Click Paradox: Semantic vs. Physical vs. Macros

When interacting with UI elements (especially in Electron apps), there is a hierarchy of reliability.

1. **Keyboard Macros (The Ultimate Bypass):**
   - **Why:** Pure keyboard macros bypass all UI occlusion, bounding box errors, and DFS requirements.
   - **How:** Use universal shortcuts (`Cmd+K` for search), write strings to the clipboard (`clipboard-set`), and paste them (`Cmd+V`). 
   - **Performance:** Executes in seconds compared to 30+ seconds for a DFS drill-down.

2. **Physical Coordinate Clicks (`mouse-click --xy`):**
   - **Why:** Semantic clicks (`AXPress`) often fail in React/Electron apps.
   - **How:** Run snapshots with `--include-bounds`. Calculate the center pixel (`x + width/2`, `y + height/2`) and issue a raw hardware click.
   - **The Offscreen Trap:** If an element has `height: 0` or `states: ["offscreen"]`, you must use `scroll-to` first, wait for the animation, take a *fresh* snapshot, re-calculate the bounds, and *then* click.

---

## 4. General Reliability & Focus Management

- **Keystroke Leakage:** When issuing physical keystrokes (`press cmd+v`, `return`) or physical coordinate clicks, macOS can sometimes shift focus back to the terminal running the script. This causes your automation to type into your shell instead of the app or interrupt the user's workflow.
  - **The Fix:** **ALWAYS** call `osascript -e 'tell application "<AppName>" to reopen' -e 'tell application "<AppName>" to activate'` explicitly right before starting **every** typing sequence, keyboard macro, or physical mouse click. Calling `reopen` forces macOS to recreate and un-minimize the main window if all windows were closed. Do not rely solely on `agent-desktop focus-window` as it can fail on opaque or ghost windows.
  - **The Semantic Exception:** **NEVER** use `osascript` activation when dispatching synthetic semantic clicks (like `AXPress` via `agent-desktop click <ref_id>`). Semantic clicks work perfectly in the background. Activating the app first will unnecessarily steal the user's focus and interrupt their typing.

- **Role Variations:** UI lists (contacts, search results) can dynamically change roles (`button`, `cell`, `statictext`). When grepping the tree, match on multiple likely roles instead of hardcoding just one.

- **Stealth Clicks:** When performing physical coordinate clicks, **ALWAYS** use the custom `stealthClick(x, y)` wrapper from `utils/mouse.py` (or `utils/mouse.js` for legacy tasks). 
  - **Why:** It captures the user's physical mouse position, performs the click instantly via a compiled Swift CoreGraphics binary, and returns the pointer to the user's hand within milliseconds, preventing workflow interruption.

---

## 5. Data Handling

- **Never summarize JSON snapshots.** When a tree is captured, save it as a pretty-printed file to disk and inform the user of the path. Let the user inspect the structure themselves.
- **The DFS Rule (Never use Compact):** Never use `agent-desktop snapshot --compact`. It truncates the tree and hides actionable elements. Always run a full DFS (Depth-First Search) tree extraction. For each snapshot, construct one complete DFS tree and format it in place instead of running endless granular drill-downs.

---

## 6. Harness Logging & State-Diff Workflow Tracking

- **Sequence of (tree_state, action):** Every LLM_OS workflow is captured as a sequence of state-action tuples: $(S_0, A_1 \to S_1, A_2 \to S_2 \dots)$.
- **Git-Style Unified Diffs:** Instead of storing bloated duplicate JSON snapshot files after every single action, the harness computes git-style unified diffs (`+` additions, `-` deletions, `@@` line headers).
- **Transient Ephemeral Stripping:** Normalizing JSON tree representation by removing random snapshot IDs and session prefixes (`@s1faoqstpdf3hc:e1` $\rightarrow$ `:e1`) keeps execution logs focused purely on structural and semantic UI state changes.
- **Harness Logger (`utils/harness_logger.py`):** Provides a clean API (`start_workflow`, `log_action`, `finalize`) for task scripts to produce single, human-comprehensible workflow log files (`workflow_execution.diff.log`).

---

## 7. Outbound Action & Recipient Verification

- **The Danger of Unverified Selection:** Selecting a contact via search or keyboard macros can fail or default to the previously active chat window. Dispatches without header checks will send messages/media to the wrong recipient.
- **Mandatory Header Verification Pattern:**
  - Before typing or pasting into any message field, perform a snapshot and locate the active chat header title (`role: button` or `role: statictext` at the top of the chat area).
  - Verify that `target_recipient.lower()` matches `active_header_title.lower()`.
  - If they do NOT match, **halt execution immediately** (`RECIPIENT_MISMATCH_ERROR`) to protect user privacy and prevent wrong dispatches.

---

## 8. Cognitive Agent Brain vs Hardcoded Script Runner

- **The Anti-Pattern (Blind Script Execution):** Blindly executing fixed string matches or grabbing `results[0]` in search results without reasoning about candidate identity causes wrong dispatches when multiple contacts exist (e.g. `Vivek CSE B311` vs `Vivek CSE B313`).
- **The Cognitive Agent Loop (LangGraph State Machine):**
  - **Perceive:** Capture full state $S_t$ and extract all matching candidate nodes.
  - **Evaluate Match Confidence:** If multiple candidates match a search query, or if the match is ambiguous, **PAUSE AND ASK THE USER FOR CLARIFICATION**.
  - **Act & Verify:** Only execute once target recipient identity is 100% disambiguated and verified.

---

## 9. Rich Text & Formatted Content Injection (The HTML -> RTF -> NSPasteboard Pattern)

- **The Problem:** Direct typing or pasting raw Markdown syntax into desktop editors (MS Word, Apple Pages, Notes, Mail, TextEdit) fails because text engines treat Markdown characters (`#`, `**`) as literal text.
- **Universal Injection Pipeline:**
  1. **Compose Payload in HTML:** Structure headers (`<h1>`), bold text (`<b>`), and lists (`<ul><li>`) using standard HTML.
  2. **Compile to Native RTF:** Run macOS `textutil -convert rtf content.html` to generate a compiled Rich Text document.
  3. **Load Native Pasteboard Type:** Load RTF bytes directly into macOS `public.rtf` pasteboard using AppleScript:
     ```bash
     osascript -e 'set the clipboard to (read (POSIX file "content.rtf") as "RTF ")'
     ```
  4. **Paste into Canvas:** Send `agent-desktop press cmd+v` to paste.
- **Result:** Delivers 100% fidelity headings, weights, and styling across any native rich-text canvas without brittle GUI formatting menu interaction.

---

## 10. Native Modal Sheets & File Pickers (Open, Save, Go-To)

- **Universal Save Dialog Pattern (`Cmd+S`):**
  - Modal save sheets (`role: sheet`, `native_id: save-panel`) expose an accessible text field for the filename (`native_id: saveAsNameTextField`).
  - **Best Practice:** Use direct semantic mutation `agent-desktop set-value <ref_id> "filename"` directly on `saveAsNameTextField`, then trigger a semantic click on the confirmation button (`native_id: OKButton` / `Save`). This completely bypasses folder-jumping race conditions.
- **Universal Open / Workspace Picker Pattern (`Cmd+O`):**
  - Native file picker sheets (`role: sheet`, `native_id: open-panel`) support the native "Go to the folder" path jumper.
  - **Best Practice:** Trigger `Cmd+O` $\to$ dispatch `Cmd+Shift+G` $\to$ write absolute target path to clipboard (`clipboard-set`) $\to$ paste (`Cmd+V`) + `Return` $\to$ confirm with `Return` (or click `OKButton` / `Open`).
  - **Verification:** Inspect the main window title transitioning to `<Document/Welcome> — <WorkspaceName>` in the accessibility tree.

---

## 11. Browser & Web Application Automation Primitives

- **Isolated / Private Browsing Sessions:**
  - Standard shortcut `Cmd+Shift+N` (Chromium, Brave, Arc, Safari) launches a dedicated private/incognito window with an isolated session and clean cache.
- **Omnibox Address Bar Targeting (`Cmd+L`):**
  - In all browsers, `Cmd+L` unconditionally focuses and selects the address bar textfield regardless of what web element was previously active or if popups are open.
  - Pair with `clipboard-set` + `Cmd+V` + `Return` for fast, deterministic URL navigation.
- **Page Load Verification:**
  - After navigating, poll the accessibility tree for `role: webarea` and target domain static text nodes to verify that DOM rendering has completed before dispatching downstream interactions.

---

## 12. Preference Panes & Dynamic Combobox Controls

- **Direct Preference Deep-Linking (`x-apple.systempreferences:`):**
  - Target preference screens directly using extension URLs (e.g., `open "x-apple.systempreferences:<extension-id>"` such as `com.apple.Lock-Screen-Settings.extension` or `com.apple.Battery-Settings.extension`). This avoids fragile sidebar navigation and guarantees the target preference surface is immediately active.
- **Combobox & Pop-up Menu Selection Pattern:**
  - Native AppKit/SwiftUI comboboxes (`role: combobox`) expose their current selection via the `value` attribute.
  - **Interaction Flow:**
    1. Compute bounds center and dispatch `stealth_click` on the combobox to expand the menu.
    2. In the resulting modal popup list (`role: menuitem`), click the target item directly or type the prefix character followed by `Return`.
    3. Verify state mutation by checking the combobox `value` attribute update in the subsequent accessibility snapshot.

---

## 13. Notion Page Navigation & Quick Find Pattern (`Cmd+P`)

- **The Problem:** Notion sidebar and tab list elements are dynamically rendered within deeply nested Electron web containers. Physical coordinate clicks can be dropped if Chromium processes synthetic mouse events asynchronously or if sidebar tabs undergo rerenders.
- **Universal Notion Page Navigation Pattern:**
  1. **Activate App:** Explicitly activate Notion via `osascript -e 'tell application "Notion" to activate'`.
  2. **Trigger Quick Find:** Dispatch `agent-desktop press cmd+p` (or `Cmd+K`) to open the native Quick Find modal search dialog (`role: dialog`, `name: 'Search Notion'`).
  3. **Inject Search Query:** Set the clipboard to the target page name (`agent-desktop clipboard-set "<Page Name>"`), paste via `agent-desktop press cmd+v`, and confirm with `agent-desktop press return`.
  4. **State Verification:** Poll the accessibility tree (`capture_full_dfs_tree`) for `role: webarea` matching `<Page Name>` and ensure page content textfields populate.
