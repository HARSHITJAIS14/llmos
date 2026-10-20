# Electron / React desktop apps (Notion, VSCode, Slack)

<!-- provenance: ATree_tool days 1-5, Notion 3.x + VSCode, agent-desktop 0.4.0, macOS 15 -->

Hostile to the AX API: the DOM is truncated behind a generic webarea
(e.g. `notion-app`, `children_count: 4` with no children serialized).

## Strategy ranking (fastest first)
1. **Keyboard macros** — bypass all occlusion, bounds errors, and drill-downs.
   `Cmd+K`/`Cmd+P` search, `clipboard-set` + `Cmd+V` paste, `Return`. Seconds
   vs 30+ s of tree traversal. Always try this route first.
2. **Physical coordinate click** (`mouse-click --xy`, via the stealth-click
   pattern) — compute center from bounds: `(x + w/2, y + h/2)`.
3. **Semantic `click <ref>` (AXPress)** — LAST. Silently swallowed by React
   routing: returns `ok: true`, changes nothing. Declare a postcondition and
   let the verify hook catch it.

## Tree access
- Full snapshots only when drilling: `--skeleton`/`--compact` strip the
  `ref_id`s you need for `snapshot --root`.
- Drill-down: find nodes with `children_count > 0` but no `children`, run
  `snapshot --root <ref> --snapshot <snapshot_id>` to force Chromium to
  serialize. Use `core.snapshot.expand_truncated` (bounded), never a blanket
  `--max-depth 40` (that is how a 1.9 MB Notion tree happened).

## Known traps
- **Ghost windows**: multiple windows titled "Notion", all `visible: false`,
  all timing out. Filter `list-windows` for `visible: true` + a real title;
  pass `--window-id` explicitly. `AMBIGUOUS_TARGET` means you skipped this.
- **Offscreen nodes**: `height: 0` or `states: ["offscreen"]` → `scroll-to`
  first, take a FRESH capture, recompute bounds, then click.
- **Space suspension**: an app in a non-active full-screen Space is suspended
  and its AX bridge locks up (`APP_UNRESPONSIVE`, NSWorkspace timeouts).
  Bring it to the active Space before querying.
