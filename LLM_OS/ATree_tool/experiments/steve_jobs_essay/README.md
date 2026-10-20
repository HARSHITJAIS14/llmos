# Steve Jobs Essay Automation Experiment

**Goal**: To automate the writing of an essay about Steve Jobs into MS Word in `.docx` format, ensuring the text is "well formatted" and the script acts as a reactive cognitive loop.

**Why**: To validate that LLM_OS can drive native applications like Microsoft Word, maintain complex rich text formatting (RTF), and use cognitive looping to safely interact with dynamic UI components (like the macOS Save Dialog) using Python orchestration and harness logging.

**What was done**:
1. A markdown essay about Steve Jobs was generated.
2. The `textutil` CLI was used to natively convert the markdown to RTF.
3. AppleScript (`osascript`) was used to load the generated RTF into the macOS clipboard to preserve all rich text formatting (bolding, headers).
4. `agent-desktop` semantic commands were orchestrated through Python. We fetched full accessibility snapshots via `utils.dfs_tree.capture_full_dfs_tree` at each state change.
5. Paging and save triggers (`cmd+v`, `cmd+s`) were simulated natively.
6. A dynamic loop polled for the `save-panel` sheet. Once detected, we utilized semantic `set-value` to insert the document name and `click` to engage the Save button.

**Results / Learnings**:
- Using AppleScript to set the clipboard via `(read (POSIX file "essay.rtf") as "RTF ")` correctly populates the macOS `public.rtf` Pasteboard format, ensuring Word accepts the pasted text with styles perfectly applied.
- The `saveAsNameTextField` native ID inside Word's save sheet is the exact element for direct `set-value` invocation. This completely avoids the instability of simulating `cmd+shift+g` for folder selection.
- All actions were properly logged as GIT-style semantic diffs in `workflow_execution.diff.log` using the `HarnessLogger`.
