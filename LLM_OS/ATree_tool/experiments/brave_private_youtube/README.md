# Brave Browser Private Window YouTube Automation Experiment

**Task**: Open `Youtube.com` in a private window in Brave Browser.

**Why**: To automate private browsing sessions and URL navigation in Brave Browser using keyboard shortcuts, clipboard injection, and full DFS state-diff tracking.

**What was done**:
1. Activated/reopened `Brave Browser` using `osascript`.
2. Captured initial baseline accessibility state $S_0$.
3. Triggered `Cmd+Shift+N` to launch a new Private Window session.
4. Captured $S_1$ to record the private window creation transition.
5. Focused address bar via `Cmd+L`, pasted `https://www.youtube.com`, and dispatched `Return`.
6. Monitored accessibility tree until YouTube webarea and DOM elements were fully rendered ($S_2$).
7. Logged all state mutations to `workflow_execution.diff.log`.
