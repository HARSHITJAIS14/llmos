---
description: Open a folder workspace in VS Code via the native picker (compiled route, verified)
argument-hint: <absolute folder path>
---

Open $ARGUMENTS as a VS Code workspace. Compiled from the verified ATree_tool
task, with its two known defects fixed: predicate waits replace every
`time.sleep()`, and the final check is a typed `title_matches` — the old
`folder_name in str(tree)` substring check reported success while the picker
was still open.

1. **Activate**: `osascript -e 'tell application "Visual Studio Code" to reopen' -e '... activate'`
2. **Open panel**: declare postcondition
   `node_exists {role: "sheet", native_id: "open-panel"} app="Visual Studio Code"`,
   then `agent-desktop press cmd+o` followed by
   `agent-desktop wait --window "Open" --timeout 5000` (predicate, not sleep).
3. **Go-to path** (dialogs.md pattern): `press cmd+shift+g`, then
   `clipboard-set "<path>"`, `press cmd+v`, postcondition
   `value_contains {value: "<path>"}` on the path text field.
4. **Confirm twice**: `press return` (accept path), `press return` (open),
   with final postcondition:
   `title_matches {pattern: "<basename>\\s*[—-]"} app="Visual Studio Code"` —
   the window title must become `<basename> — ...`. The path sitting in a
   picker text field will NOT satisfy this; that is the point.
5. Report the verified title and turns used.
