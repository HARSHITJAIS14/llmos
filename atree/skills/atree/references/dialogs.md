# Native modal sheets & file pickers (any app)

<!-- provenance: ATree_tool days 5-6, MS Word + VSCode + Finder, agent-desktop 0.4.0 -->

## Save dialog (`Cmd+S`)
Sheet: `role: sheet`, `native_id: save-panel`; filename field
`native_id: saveAsNameTextField`.
Best practice: `set-value <ref> "filename"` directly on the field (bypasses
folder-jumping races), then semantic click `native_id: OKButton` / "Save".

## Open / workspace picker (`Cmd+O`)
Sheet: `native_id: open-panel`. Use the Go-To path jumper:
`Cmd+O` → `Cmd+Shift+G` → `clipboard-set <absolute path>` → `Cmd+V` →
`Return` (accept path) → `Return` (confirm open).

## Verification
Postcondition is a `title_matches` on the MAIN window
(`<Document> — <Workspace>`), never a substring scan — the path text sits in
the picker's own field and will substring-match while the open has failed.

## Preference panes
Deep-link, never navigate the sidebar:
`open "x-apple.systempreferences:<extension-id>"`
(e.g. `com.apple.Lock-Screen-Settings.extension`). Comboboxes: click to
expand, pick `role: menuitem`, verify the combobox `value` attribute changed.
