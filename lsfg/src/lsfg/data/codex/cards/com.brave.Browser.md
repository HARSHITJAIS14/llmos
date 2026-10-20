## Brave Browser (com.brave.Browser) · chromium_browser
Anchors: groupdom#root web page root container · toolbardom#view_1000 main browser toolbar · buttondom#view_1001 back button · buttondom#view_1002 forward button · buttondom#view_1003 reload button · buttondom#view_1005 bookmark this tab button · textfielddom#view_1012 address and search bar · imagedom#view_1011 address bar search icon · comboboxdom#view_1006 extensions menu · comboboxdom#view_1007 main app menu · comboboxdom#view_1009 toolbar extension button · toolbardom#view_1025 bookmarks bar
Quirk depth_capped_husk: recapture same window at --max-depth 40, no activation
Quirk thumbnail_proxy_window: use WS title only; bounds from AX root; activate before coordinate actions
Quirk disabled_keeps_click: gate on disabled state, not on Click
Quirk window_id_drift: re-pick window by ghost filter each session; never cache window id
Quirk readonly_control_as_button: Click/Expand it; never type into it
Its window is often hidden: the executor activates it before typing or pointer clicks.
