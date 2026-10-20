# Agent Behavioral Rules

## Workflow Organization & Language

1. **Language Paradigm (Python):** From now onwards, all new scripts, orchestrations, and experiments must be written in **Python**. Do not use Node.js (`.js`). Python provides superior built-in modules (`json`, `subprocess`) for OS-level orchestration. Existing tasks in `.js` remain as-is for now, but any net-new logic must be `.py`.
2. **Experiments First:** Whenever developing a new feature, testing an API, or writing a script, **always** start by placing the code in the `experiments/` directory.
2. **Subfolder per experiment:** Each experiment gets its own subfolder inside `experiments/`. Every subfolder must contain:
   - The script(s) used to run the experiment
   - The raw output files (JSON snapshots, logs, etc.)
   - A `README.md` explaining what was done, why, and what was found
3. **Reuse scripts:** Never rewrite a script that already exists in `experiments/`. Check the subfolder first and reuse or extend what's there.
4. **Promote to Tasks:** Once an experiment is successful and verified, consolidate the logic, add proper documentation/description at the top of the file, give it a clean filename, and move it to the `tasks/` directory.
5. **Clean Workspace:** Never leave scratch scripts, JSON dumps, or failed tests in the root directory or directly in `experiments/`. They must live in a named subfolder.

## Snapshots & Raw Output

6. **Never summarize snapshots without being asked.** When a snapshot or raw JSON is captured, save it as a pretty-printed file and tell the user the path. The user will scroll through it themselves.
7. **Always pretty-print JSON snapshots** before saving so the user can read them comfortably in their editor.
8. **The Full DFS Rule (Never use Compact):** Never use `agent-desktop snapshot --compact` or `--skeleton` (they truncate trees and strip actionable `ref_id`s/nodes). Always run full DFS (Depth-First Search) tree extraction (via `utils.dfs_tree.capture_full_dfs_tree`) so every snapshot captures the 100% complete expanded accessibility tree across all steps.

## Verified Tasks (in `tasks/`)

| Script | Description |
|---|---|
| `open_finder_file.js "<filename>"` | Opens any file visible in Finder by searching the AX tree and physical double-clicking |
| `click_notion_library.js` | Navigates to the Library tab in Notion via DFS + scroll-to + coordinate click |
| `send_whatsapp_message.js "<contact>" "<message>"` | Sends a WhatsApp message to any contact via search + compose + Enter |
| `obs_start_recording.py` | Silently launches OBS in background and clicks Start Recording via AXPress |
| `obs_stop_recording.py` | Clicks Stop Recording via AXPress stealthily in the background |
| `add_calendar_event.py "<event_text>"` | Reopens Calendar, triggers Quick Event (`Cmd+N`), forces Event tab mode via `stealthClick`, and pastes event details |
| `open_fotmob_scorecard.py "<match_query>"` | Opens FotMob match scorecard on Safari with full DFS state-diff workflow logging |
| `write_word_document.py "<filename>" "<html>"` | Activates MS Word, pastes HTML as preserved RTF, and executes cognitive loop to navigate the Save dialog natively |
| `open_vscode_folder.py "<folder_path>"` | Opens any folder workspace in Visual Studio Code via native open dialog sheet and state-diff tracking |
| `open_brave_private_url.py "<url>"` | Launches a dedicated Private Window in Brave Browser, navigates to target URL, and verifies DOM state |
| `set_sleep_timeout.py "<minutes>"` | Opens System Settings Lock Screen pane and configures display/sleep inactivity timeout |


## App-Specific Automation Rules

### Native/Catalyst Apps (Finder, WhatsApp, Safari, Calendar)
- Full AX tree in **one** snapshot — no DFS needed.
- Finder: pick the window with a real title (not "Finder"). Use `--window-id`.
- WhatsApp: Catalyst apps don't appear in `list-windows --app`. Use global `list-windows` and filter by title containing "WhatsApp".
- Calendar: Background extension processes cause global `list-windows` timeouts. Use `snapshot --surface popover` to inspect popovers directly and `stealthClick()` the `QuickEventNewEventButton` tab to prevent defaulting to Reminders mode.

### Electron Apps (Notion)
- AX tree is truncated behind the `notion-app` webarea. DFS drill-down required.
- Use full snapshots only — `--skeleton` and `--compact` strip `ref_id`s.
- Ghost windows (titled "Notion", `visible: false`) all timeout. Pick the real window by title.
- Semantic click (`AXPress`) is silently swallowed by React. Must use physical `mouse-click --xy`.
- If a node is `offscreen` with `height: 0`, run `scroll-to` first, then re-snapshot for fresh bounds.
- **Keyboard macros (Cmd+K search + clipboard paste) are fastest and bypass all Electron limitations.**

### Browser Apps (YT Music in Safari)
- Open the URL directly with `open "<url>"`. Browser AX tree is native — one snapshot works.
- Search for buttons/links by name, click via coordinate.
### General Reliability & Focus Management
- **Keystroke Leakage:** When issuing physical keystrokes (`--headed press cmd+v`, `return`) or physical coordinate clicks, macOS can sometimes shift focus back to the terminal running the script, causing keystrokes to leak into the shell or interrupting the user's workflow.
- **The Fix:** **ALWAYS** call `osascript -e 'tell application "<AppName>" to reopen' -e 'tell application "<AppName>" to activate'` explicitly right before starting **every** typing sequence, keyboard macro, or physical mouse click. Calling `reopen` forces macOS to recreate and un-minimize the main window if all windows were closed. 
- **The Semantic Exception:** **NEVER** use `osascript` activation when dispatching synthetic semantic clicks (like `AXPress` via `agent-desktop click <ref_id>`). Semantic clicks work perfectly in the background. Activating the app first will unnecessarily steal the user's focus and interrupt their typing.
- **Role Variations:** List items (like contacts or search results) can vary in roles (`button`, `cell`, `statictext`). When finding nodes, match on multiple likely roles instead of hardcoding one.
- **Stealth Clicks:** When performing physical coordinate clicks (`mouse-click --xy`), **ALWAYS** use the `stealthClick(x, y)` wrapper from `utils/mouse.py` (or `utils/mouse.js` for legacy tasks). This guarantees that the user's physical mouse position is captured, the click is performed instantly, and the pointer is returned to the user's hand within milliseconds, preventing workflow interruption.

### Cognitive Brain Architecture & Disambiguation Rules
1. **Be the Cognitive Brain (Perceive $\rightarrow$ Reason $\rightarrow$ Disambiguate $\rightarrow$ Act $\rightarrow$ Verify):**
   - LLM_OS operates as an intelligent cognitive state-machine agent, not a static, hardcoded script runner.
   - At every step: capture state $S_t$, perceive all candidate elements, reason about match confidence, and verify state transitions.
2. **Mandatory Disambiguation over Guesswork:**
   - **NEVER GUESS AMBIGUOUS TARGETS:** If a search query (e.g. "Vivek CSE") matches multiple candidate elements/contacts (e.g., `Vivek CSE B311`, `Vivek CSE B313`, `201133 Vivek Agrawal BT-CSE`), or if the target recipient is ambiguous, **THE AGENT MUST STOP AND ASK THE USER FOR CLARIFICATION** (presenting the candidate options) instead of picking the first match blindly!
   - High-stakes outbound actions (sending text messages, media, emails, financial transactions) **REQUIRE EXPLICIT RECIPIENT CLARIFICATION** whenever multiple contact candidates exist.

### Critical Safety Rule: Outbound Recipient Verification
- **NEVER DISPATCH BLINDLY:** Before executing any outbound action (sending a text message, pasting media/images, emailing, submitting forms, or deleting items), **ALWAYS inspect the accessibility tree to verify that the active chat header or container title matches the target recipient!**
- **Verification Method:** Inspect the chat header / title bar node in the AX tree. If the active chat title does **NOT** match the target contact name, **ABORT IMMEDIATELY** and raise an explicit `RECIPIENT_MISMATCH_ERROR`. Never assume a search click or Return key succeeded without inspecting the active chat header.



## Harness Logging & State-Diff Workflow Tracking

- **Sequence Representation:** Every task execution is modeled as a sequence of `(tree_state, action)` transitions $S_{t-1} \xrightarrow{A_t} S_t$.
- **Full DFS Tree at Each Step:** Every state $S_t$ must be captured using full DFS tree extraction (`utils.dfs_tree.capture_full_dfs_tree`) to ensure 100% complete, un-truncated tree representations before and after every action.
- **Git-Style State Diffs:** Instead of saving whole duplicate JSON files per action step, use `utils/harness_logger.HarnessLogger` and `utils/state_diff.generate_git_diff`.
- **Diff Formatting:** Log steps with git-style unified diffs (`+` additions, `-` deletions, `@@` line breaks) and strip ephemeral snapshot hash prefixes (`strip_ephemeral=True`) so logs highlight meaningful UI mutations.
- **Log File Storage Location:** 
  - For **Experiments**: Stored inside the subfolder as `experiments/<subfolder>/workflow_execution.diff.log`.
  - For **Verified Tasks**: Stored inside `tasks/logs/` as `tasks/logs/<task_name>_<timestamp>.diff.log`.




