# VS Code Open Folder Experiment

**Task**: Open LLM_OS folder in VS Code via GUI Accessibility Automation.

**Why**: To automate workspace folder opening in Visual Studio Code (an Electron-based editor) using the cognitive reactive loop, keyboard macro navigation on the native macOS open sheet, and full DFS state-diff tracking.

**What was done**:
1. Activated and reopened `Visual Studio Code` using `osascript`.
2. Captured baseline DFS state $S_0$.
3. Sent `Cmd+O` to invoke the native open dialog sheet.
4. Sent `Cmd+Shift+G` to invoke the "Go to the folder" path input.
5. Populated the clipboard with the absolute target path (`/Users/harshit/Desktop/YC/LLM_OS`) and pasted via `Cmd+V`, followed by `Return`.
6. Submitted the open selection via `Return`.
7. Verified the updated VS Code workspace title and tree structure displaying `LLM_OS`.
8. Generated the full sequence of git-style state diffs in `workflow_execution.diff.log`.
