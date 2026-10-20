# Experiment: FotMob Barcelona vs Elche Scorecard in Safari

## Overview
This experiment automates navigating to and opening the **Barcelona vs Elche La Liga Match Scorecard on FotMob** using Safari on macOS.

In accordance with LLM_OS architecture rules:
- **Language**: Written in Python (`fotmob_scorecard.py`).
- **Full DFS Accessibility Tree**: Uses `utils.dfs_tree.capture_full_dfs_tree` at every step to build un-truncated AX trees.
- **Stealth Coordinate Clicks**: Uses `utils.mouse.stealth_click` for hardware clicks.
- **Git-Style State-Diff Logging**: Tracks workflow steps $(S_0 \xrightarrow{A_1} S_1)$ and logs unified line diffs to `workflow_execution.diff.log` via `utils.harness_logger.HarnessLogger`.

## File Inventory

| File | Description |
|---|---|
| `fotmob_scorecard.py` | Python automation script launching Safari, searching FotMob match, capturing full DFS AX tree, clicking match link, and logging state diffs |
| `workflow_execution.diff.log` | Unified git-style execution diff log showing tree mutations before and after navigation |
| `README.md` | Experiment documentation and verification report |

## How to Run

```bash
python3 experiments/fotmob_barcelona_elche/fotmob_scorecard.py
```

## Verification Summary
- **Safari Execution**: Safari successfully reopened, activated, and navigated to FotMob's Barcelona vs Elche match scorecard page.
- **State-Diff Logging**: Complete 13,000+ line git-style unified diff logged to `workflow_execution.diff.log`.
