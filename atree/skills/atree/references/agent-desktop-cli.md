# agent-desktop CLI: the flags that matter and the traps that bite

<!-- provenance: 2026-08-29 live session, agent-desktop 0.8.1 -->

Prefer `ax` (observe/find/do). Reach for raw agent-desktop only for waits,
window management, clipboard, and batch. Everything prints a JSON envelope:
`{"ok": true, "data": ...}` or `{"ok": false, "error": {code, message, suggestion}}`.

## Traps (each one cost real turns in a live session)

- **`press`/`type` take NO `--app` or `--window-id`** — keystrokes go to the
  focused app, period. Activate first (`osascript ... reopen/activate`), or
  keystrokes leak into the terminal. `ax do` handles activation for you.
- **`--compact` and `--skeleton` strip `ref_id`s** — a compact tree cannot be
  clicked semantically. Get refs from `ax find` or a full `snapshot --root` drill.
- **`screenshot` takes the output path as a POSITIONAL arg**, not `--output`:
  `agent-desktop screenshot --app X --window-id w-1 /path/out.png`
- **`AMBIGUOUS_TARGET`**: many apps keep ghost windows (`visible: false`).
  `list-windows --app X`, pick `is_focused`/`visible: true`, pass `--window-id`.
  (`ax observe` does this automatically.)
- **Non-active Space = stub tree**: window reports focused+visible but every
  node is `offscreen` and unnamed, or snapshot fails with
  `window_without_accessibility_element`. Activate the app, then re-observe;
  `--surface focused --app X` is the reliable scope right after a Space switch.
- **`wait --window <title>` matches exactly** — "(8) YouTube" does not match
  "YouTube". Prefer `wait --text` or an `ax do` postcondition.

## Worth knowing

- `wait --element <ref> --predicate actionable`, `wait --text "..."`,
  `wait --event <kind>` — predicates, never sleep.
- `batch '[{"command":"press","args":{...}}, ...]'` — several steps, one call.
- `clipboard-set "text"` + `press cmd+v` — the fast path for entering text.
- `find --app X --name "..." --role button --limit 20` — targeted search;
  `ax find` wraps it with a tree-walk fallback.
- `launch <app>` / `close-app <app>` / `focus-window` / `list-windows`.
- `snapshot --surface popover|sheet|menu` — scope to transient UI directly.
