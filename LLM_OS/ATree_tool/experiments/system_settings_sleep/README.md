# System Settings Sleep Timeout Automation Experiment

**Task**: Increase the display / system sleep timeout in macOS System Settings to 30 minutes.

**Why**: To automate macOS System Settings preferences (AppKit/SwiftUI preference pane) using direct pane URL invocation (`x-apple.systempreferences:com.apple.Lock-Screen-Settings.extension`), accessibility node perception, popup menu interaction, and state-diff tracking.

**What was done**:
1. Invoked System Settings directly to the Lock Screen settings pane using `x-apple.systempreferences:com.apple.Lock-Screen-Settings.extension`.
2. Captured initial baseline accessibility state $S_0$.
3. Located the "Turn display off on battery when inactive" combobox control.
4. Interacted with the dropdown menu via `stealth_click` / selection macro to choose the `For 30 minutes` option ($S_1$).
5. Verified the updated combobox value (`For 30 minutes`) in the accessibility tree ($S_2$).
6. Tracked unified line diffs in `workflow_execution.diff.log`.
