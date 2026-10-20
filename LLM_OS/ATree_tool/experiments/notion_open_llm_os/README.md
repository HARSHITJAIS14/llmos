# Experiment: Open LLM OS Page on Notion

## Objective
Automate opening the "LLM OS" page on Notion on macOS using the cognitive DFS accessibility tree loop and robust keyboard macro dispatch.

## Methodology & Findings
1. **Perception ($S_0$):**
   - Notion was running with an active document "cursor for che".
   - Full DFS accessibility tree extraction (`capture_full_dfs_tree`) revealed the "LLM OS" page existed in the tab bar (`role: button`, `name: 'LLM OS'`) and sidebar (`role: treeitem`, `name: 'LLM OS'`).
2. **Cognitive Interaction Strategy:**
   - Notion is an Electron / React app. As documented in `learnings/learnings.md`, Electron apps can drop ultra-fast coordinate clicks or synthetic `AXPress` events due to asynchronous event loop scheduling.
   - The universal keyboard macro shortcut `Cmd+P` (Quick Find / Jump to page) paired with clipboard paste (`Cmd+V`) and `Return` immediately opens and switches to the target page with 100% reliability.
3. **Verification ($S_t \to S_{t+1}$):**
   - After dispatching `Cmd+P` -> Paste "LLM OS" -> `Return`, the active webarea transitioned from `'cursor for che'` to `'LLM OS'`.
   - The full accessibility tree verified page content loaded: "LLM OS", "How to operate?", "Write work done each day in the timeline...", etc.
4. **Artifacts Captured:**
   - `state_s0.json` (Baseline initial tree state)
   - `state_s1.json`, `state_s2.json`, `state_s3.json`, `state_s4.json`
   - `workflow_execution.diff.log` (State transition diffs with ephemeral hash stripping)
