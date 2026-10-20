## Firefox (org.mozilla.firefox) · gecko
Anchors: toolbardom#nav-bar navigation toolbar · buttondom#back-button back button · buttondom#forward-button forward button · buttondom#reload-button reload button · buttondom#sidebar-button sidebar toggle button · groupdom#urlbar address bar container · buttondom#fxa-toolbar-menu-button account menu button · buttondom#unified-extensions-button extensions menu button · buttondom#alltabs-button list all tabs button · buttondom#PanelUI-menu-button app menu (hamburger) button · toolbardom#PersonalToolbar bookmarks toolbar · buttondom#PlacesChevron more bookmarks overflow button
Quirk depth_capped_husk: recapture same window at --max-depth 40
Quirk click_everywhere: filter actionable by role, not by Click
Quirk ambiguous_process: address by window id or parent pid, never --app name
Quirk thumbnail_proxy_window: match window by title; take bounds from AX root
Quirk ghost_only_window_list: snapshot anyway; use AX root bounds
Its window is often hidden: the executor activates it before typing or pointer clicks.
