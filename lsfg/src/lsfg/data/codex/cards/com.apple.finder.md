## Finder (com.apple.finder) · appkit
Anchors: window#FinderWindow Finder browser window root · browser#ColumnView column-view file browser · unknown#statusBar window status bar
Quirk enumeration_partial: trust the prefix; scroll the list scrollarea or use Go to Folder / search, then re-snapshot
Quirk ghost_only_window_list: snapshot anyway; take bounds from the AX root
Quirk textfield_is_label: treat as statictext; never SetValue
Quirk identity_in_value: resolve file items by norm(value) + nth
Quirk offscreen_needs_container_scroll: Scroll nearest scrollarea/browser ancestor, re-snapshot
