## Notes (com.apple.Notes) · appkit
Anchors: textfield#"Note Body Text View" note body editor · scrollarea#"Note Body Scroll View" note body scroll container · table#ICMNoteListTableView_asList note list table · cell#ICMNoteListCell note list row cell · unknown#FolderCell sidebar folder cell wrapper
Quirk document_as_single_value: read the whole value and split on U+2028 and newline; append with TypeText, never SetValue (replaces the whole note)
Quirk disabled_keeps_click: check the disabled state before clicking; Click presence proves nothing
Quirk readonly_control_as_button: activate the window and re-snapshot; foreground it gains SetValue+SetFocus. Never type into it while readonly
Quirk mass_focused: real focus is the focused container (outline/table), not its items
Quirk window_id_drift: re-pick the window by title/bounds each session
