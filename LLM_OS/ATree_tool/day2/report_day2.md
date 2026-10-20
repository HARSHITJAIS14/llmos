# Day 2: The Electron Veil and Accessibility Limits

## 1. Objective
Our goal today was to interact with Notion (a heavy Electron-based desktop application) using headless OS automation (`agent-desktop`). We specifically wanted to retrieve the entire accessibility tree (including the Kanban boards, sidebars, and timelines) and programmatically click a specific tab (the "Library" tab).

This exercise served as a real-world stress test for the theories established in Day 1 regarding React Native/Catalyst/Electron UI flaws.

---

## 2. The Experiments & The Failures

We attempted to extract the full accessibility tree and interact with Notion through several iterations. Each failure exposed a critical limitation in macOS GUI automation.

### Failure 1: The Truncated Skeleton
- **Action:** We ran `agent-desktop snapshot --app Notion -i --compact`.
- **Result:** We received a highly compressed, 14KB JSON file.
- **Why it failed:** Electron masks its internal DOM from the macOS accessibility API to save memory. When `agent-desktop` queried the tree, macOS stopped at the `notion-app` webarea, reporting a simple `children_count: 4` rather than exposing the actual React elements (buttons, Kanban cards, etc.).

### Failure 2: Ambiguous Targets & Hidden Windows
- **Action:** We tried forcing a full snapshot without the `--compact` flag: `agent-desktop snapshot --app Notion -i`.
- **Result:** Failed with `AMBIGUOUS_TARGET`.
- **Why it failed:** Electron apps often spawn multiple hidden or background windows (e.g., helpers or cached views). The OS saw 10 windows matching the title "Notion" (all marked `visible: false`), causing the headless agent to abort to avoid clicking the wrong target.
- **Fix:** Use `agent-desktop list-windows --app Notion`, find the correct `window_id` manually, and pass it via `--window-id <id>`.

### Failure 3: The Full-Screen Suspension (OS Timeout)
- **Action:** We wrote a DFS (Depth-First Search) script to forcefully drill down into the `notion-app` container.
- **Result:** Failed with `TIMEOUT: NSWorkspace app inventory timed out` and `APP_UNRESPONSIVE`.
- **Why it failed:** The user was watching a YouTube video in macOS full-screen mode on a different Space. macOS aggressively suspended Notion in the background to preserve system resources. Because it was suspended, Notion's accessibility bridge locked up, causing the entire OS accessibility query to time out.
- **Key Lesson:** macOS Space isolation is a hard constraint. An application suspended in a non-active full-screen Space cannot be queried via the Accessibility API.

---

## 3. The Breakthrough: The DFS Drill-Down

Once Notion was brought back to the active screen (exiting full-screen), we ran the DFS script again. The script recursively targeted truncated nodes and ran `agent-desktop snapshot --root <ref_id>` to force Chromium to serialize the hidden DOM.

- **Result:** Success. The script produced a massive **2.2 Megabyte JSON file** (`notion_dfs_tree.json`). It made **15 separate drill-down API calls** recursively into the `notion-app` container.
- **The Takeaway:** The data *does* exist. We successfully pierced the Electron veil.
- **The Catch:** Feeding a 2.2 MB JSON file to an LLM every time it needs to find a button is computationally disastrous (too slow, too expensive, too many tokens).

*Snippet of a recovered node from the DFS tree (The Library Tab):*
```json
{
    "available_actions": ["Click", "RightClick", "ScrollTo", "SetFocus"],
    "name": "Library",
    "ref_id": "@s3kwwaziwb5osv:e483",
    "role": "button"
}
```

*DFS Script Summary (`experiments/dfs_notion.js`):*
- Find `notion-app` node by `native_id`.
- If a node has `children_count > 0` but no `children` array → it is truncated → run `snapshot --root <ref_id>` to force-expand it.
- Merge the drill-down results back into the in-memory tree.
- Save the fully merged tree to disk.

---

## 4. The Click Paradox: Semantic vs. Physical Automation

With the `ref_id` of the Library tab acquired, we attempted to click it. This led to the most important discovery of the day.

### The Semantic Click (Silent Failure)
- **Action:** `agent-desktop click @s3kwwaziwb5osv:e483 --snapshot s3kwwaziwb5osv`
- **Result:** `agent-desktop` reported `"outcome": "succeeded"`.
- **Reality:** Nothing happened.
- **Why:** `agent-desktop` fired an `AXPress` semantic event. macOS delivered it to Notion, but Notion's internal React routing completely ignored/swallowed the synthetic event. The OS thought it succeeded, but the app ignored it.

### The Physical Click via `--headed` (Hit-Test Failure)
- **Action:** We added the `--headed` flag to force a raw, physical mouse coordinate click.
- **Result:** Failed with `Target did not become actionable within the wait budget`.
- **The Details:**
  ```json
  "check": "receives_events",
  "hit_test": {"attempted": 5, "occluded": 5},
  "occluder": {"bounds": {"height": 58.0, "width": 243.0, "x": 2560.0, "y": 1310.0}, "role": "group"},
  "reason": "occluded by group",
  "status": "fail"
  ```
- **Why it failed:** Before moving the physical mouse, `agent-desktop` performs a safety hit-test to ensure the button isn't covered by another window. Because Notion is an Electron app, it **misreports its internal bounding boxes** to macOS. The OS falsely believed that a random invisible `group` was covering the Library button, and refused to click it.

---

## 5. The `--include-bounds` Discovery: Blind Coordinate Clicks

To bypass the broken hit-test checks entirely, we discovered the `--include-bounds` snapshot flag.

- **Action:** Re-ran the DFS with `--include-bounds` added to every snapshot call.
- **Result:** Every node in the JSON now included a `bounds` object:
  ```json
  {
    "name": "Library",
    "role": "button",
    "bounds": { "x": 4176, "y": 1416, "width": 95, "height": 35 }
  }
  ```
- **The Strategy:** Instead of asking `agent-desktop` to click a *button* (which triggers hit-tests), we:
  1. Extract the button's `bounds` from the DFS tree JSON.
  2. Calculate the center pixel: `X = bounds.x + (bounds.width / 2)`, `Y = bounds.y + (bounds.height / 2)`.
  3. Fire `agent-desktop --headed mouse-click --xy <X>,<Y>` — a raw hardware mouse click that **bypasses all occlusion safety checks**.
- **Result:** Command returned `{"clicked": true, "x": 4223.0, "y": 1433.0}`.

### The Offscreen Zero-Bounds Trap
- **Problem:** Even with the center pixel calculated, the physical click sometimes hit thin air.
- **Root Cause:** The target button (Library) had `bounds: { height: 0 }` and `states: ["offscreen"]`. It was collapsed/scrolled out of view. The OS dutifully clicked the raw coordinate, but no button was actually rendered there.
- **The Fix:** 
  1. Inspect the node's `available_actions` (which included `"ScrollTo"`).
  2. Run `agent-desktop scroll-to <ref_id>` to bring it into view.
  3. **Crucial:** Wait for the animation, then take a *new* snapshot and run DFS *again* to get the updated, non-zero `bounds`.
  4. Calculate the center pixel from the *fresh* bounds and click.

### The Remaining Failure: Coordinate Space Scaling
- **Problem:** Even after scrolling, if the click visually misses on Retina or multi-monitor setups, it's a coordinate scaling issue.
- **Root Cause:** The macOS Accessibility API returns **logical points** (scaled, display-space coordinates). On a Retina or multi-monitor setup, the raw hardware coordinate system diverges:
  - A logical X of `4223` may physically correspond to `8446` at 2x Retina scale.
  - A secondary monitor offset can shift the entire coordinate origin.
- **Status:** Requires scaling calibration if logical != physical on the specific machine.

---

## 6. Final Architecture: The Winning LLMOS Click Pipeline for Electron Apps

```
Activate App
    ↓
Find visible window by title (avoid ghost/background windows)
    ↓
Full Snapshot with --include-bounds (no --skeleton/--compact)
    ↓
DFS Drill-down to expand truncated nodes in-memory
    ↓
Extract target node bounds from JSON
    ↓
If node is 'offscreen' or has 0 height/width:
    → Run scroll-to action
    → Re-snapshot & Re-DFS to get fresh bounds
    ↓
Calculate center pixel (X, Y)
    ↓
[Option A] Blind coordinate click via --headed mouse-click --xy X,Y
    → Successful! (If Retina scaling aligns)
    ↓
[Option B] Keyboard macro (cmd+k to open search, type name, press return)
    → FASTEST and most reliable, no coordinate math needed
    ↓
[Option C] Native deep link (e.g. notion://page-id)
    → Bypasses GUI entirely, most robust of all
```

---

## 7. The Keyboard Macro Breakthrough (Option B — Verified ✅)

After all the DFS/coordinate/scroll work, we discovered that **pure keyboard macros** completely bypass every Electron limitation:

- **Navigation:** `Cmd+K` opens Notion's built-in search → paste page name → `Enter` → instant navigation. No accessibility tree needed.
- **Typing:** `clipboard-set` + `Cmd+V` pastes text directly. No need to find a textbox ref_id.
- **Cursor placement:** `Cmd+End` jumps to end of page. `Enter` creates a new block.

**The entire flow for "type text into any Notion page" is:**
```
osascript → activate Notion
press cmd+k → opens search
clipboard-set "Page Name" → cmd+v → return → navigates to page
sleep 2 (page load)
cmd+End → jump to bottom
return → new block
clipboard-set "text to add" → cmd+v → pasted!
```

**Why this is superior:**
- Zero DFS drill-downs (0 vs 5-19 for coordinate approach)
- Zero coordinate math
- Zero scroll-to workarounds
- Works regardless of window position, Retina scaling, or multi-monitor setup
- Runs in ~8 seconds vs ~30+ seconds for the DFS pipeline

**Task script:** `tasks/type_in_notion.js` (promoted from `experiments/notion_type_in_docs/`)

---

## 8. Workspace Conventions Established Today

To keep the `LLM_OS` project organized as complexity grows, we formalized the following directory convention (encoded in `.agents/AGENTS.md`):

| Folder | Purpose |
|---|---|
| `experiments/` | All scratch scripts, JSON dumps, failed attempts, WIP code |
| `tasks/` | Verified, working, fully documented scripts for specific automation tasks |
| `day1/`, `day2/` | Daily research notes and reports |

**Rule:** All new code starts in `experiments/`. Only **verified, working** scripts with a proper header description get promoted to `tasks/`.

