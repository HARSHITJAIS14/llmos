# Experiment: Capture Notion Window Screenshot & Send on WhatsApp

## Overview
This experiment automates capturing a clean screenshot of the **Notion** application window and sending the image to contact **niga** ("Aryan Nigam") on **WhatsApp Desktop** (macOS).

In accordance with LLM_OS rules:
- **Language**: Written in Python (`run_task.py`).
- **Full DFS Accessibility Tree**: Uses `utils.dfs_tree.capture_full_dfs_tree` to capture un-truncated tree states before and after execution.
- **Stealth Coordinate Clicks**: Uses `utils.mouse.stealth_click` for hardware clicks.
- **Clipboard Image Dispatch**: Uses macOS native AppleScript (`set the clipboard to (read (POSIX file "...") as «class PNGf»)`) to copy the screenshot directly into the system clipboard as PNG data, followed by `Cmd+V` paste into WhatsApp.
- **Git-Style State-Diff Logging**: Tracks workflow steps $(S_0 \xrightarrow{A_1} S_1)$ and logs unified line diffs to `workflow_execution.diff.log` via `utils.harness_logger.HarnessLogger`.

## File Inventory

| File | Description |
|---|---|
| `run_task.py` | Python automation script capturing Notion window screenshot and dispatching via WhatsApp Desktop |
| `notion_screenshot.png` | Captured screenshot of the Notion window (2.6 MB PNG) |
| `workflow_execution.diff.log` | Unified git-style execution diff log showing tree mutations |
| `README.md` | Experiment documentation and verification report |

## How to Run

```bash
python3 experiments/notion_screenshot_whatsapp/run_task.py "niga"
```

## Verification Summary
- **Notion Screenshot**: Captured Notion window ID `w-70207` to `notion_screenshot.png` (2,605,627 bytes).
- **WhatsApp Dispatch**: Located contact `220227 Aryan Nigam BT-CHE`, set image to clipboard, pasted (`Cmd+V`), and dispatched image message (`Return`).
- **State-Diff Logging**: Complete git-style unified diff logged to `workflow_execution.diff.log`.
