## TextEdit (com.apple.TextEdit) · appkit
Anchors: window#open-panel open panel window root · browser#ColumnView file browser column view · menubutton#"View Options" view mode picker · menubutton#"Group or Sort By" group/sort picker · combobox#"where popup" location (Where:) popup · textfield#Search search field (the only editable textfield) · button#NewDocumentButton new document button · button#OptionsButton show options button · button#CancelButton cancel button · button#OKButton open (confirm) button
Quirk textfield_is_label: treat as statictext; never SetValue it
Quirk identity_in_value: resolve list items by norm(value)
Quirk embedded_file_browser: drive it like Finder: sidebar outline, column browser, Search field
Quirk mass_focused: real focus is the focused list/outline container, not its items
Quirk offscreen_needs_container_scroll: Scroll the nearest scrollarea or browser, then re-snapshot
