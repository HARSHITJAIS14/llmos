# Experiment: finder_snapshot

## What This Does
Captures the full macOS Accessibility Tree of the frontmost visible Finder window using `agent-desktop`, including pixel-accurate `bounds` for every interactive element.

## Why We Did This
After struggling with Notion (Electron wrapper), we pivoted to Finder — a 100% native AppKit app — to understand what a clean, healthy accessibility tree looks like.

## Key Findings
- A single `snapshot` call on Finder returns **143KB** of rich, fully expanded tree data — **no DFS loops needed**.
- Every element has real semantic roles: `treeitem`, `button`, `scrollbar`, `textfield`, `browser`, `outline`.
- Every element has accurate `bounds` out of the box (no `--include-bounds` tricks required in practice).
- `ref_count` was only 12 for the compact view — the tree is efficiently structured, unlike Notion's 2.2MB mess.
- Clicking works via plain `agent-desktop click <ref_id>` — no coordinate math, no occlusion hacks.

## Files
| File | Description |
|---|---|
| `capture_finder_snapshot.js` | Reusable script to capture and save the Finder window snapshot |
| `finder_window_snapshot_pretty.json` | Pretty-printed output from the last run |

## How to Re-Run
```bash
cd /Users/harshit/Desktop/YC/agent-desktop/npm
node /Users/harshit/Desktop/YC/LLM_OS/experiments/finder_snapshot/capture_finder_snapshot.js
```

## Snapshot Structure (Top-Level)
```
window (Recents)
  └── scrollarea
        └── outline [sidebar]
              ├── treeitem: Recents
              ├── treeitem: Documents
              ├── treeitem: Downloads
              └── ...
        └── browser [column view]
              └── scrollarea
                    └── list
                          └── textfield: <filename>   ← Clickable file items
```
