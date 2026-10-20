## Safari (com.apple.Safari) · webkit_native
Anchors: textfield#WEB_BROWSER_ADDRESS_AND_SEARCH_FIELD address and search bar · button#UnifiedField._magnifyingGlassButton search menu button in address bar · group#BackForwardSegmentedControl back/forward control group · button#SidebarButton sidebar toggle · menubutton#TabGroupPickerButton?TabGroup=* tab group picker (tail can hold a group name) · button#DownloadsButton downloads button · button#ShareButton share button · button#NewTabButton new tab button · button#TabOverviewButton tab overview button · button#customizationsPopoverButton start page customize button · unknown#TabBar?isSeparate=* tab bar container (name holds tab count) · radiobutton#TabBarTab?isPinned=* tab; query encodes pinned/narrow/active state
Quirk enumeration_partial: trust the delivered prefix; scroll the start page scrollarea or search, then re-snapshot; never drill
Quirk silent_enumeration_loss: the missing nodes cannot be located; reach items by scroll or search
Quirk hidden_window_offscreen: read is fine; activate the window and re-snapshot before any coordinate action
Quirk thumbnail_proxy_window: use its title only; take bounds from the AX root
Quirk user_data_in_id: match on the non-personal prefix; tier session for the window id
Its window is often hidden: the executor activates it before typing or pointer clicks.
