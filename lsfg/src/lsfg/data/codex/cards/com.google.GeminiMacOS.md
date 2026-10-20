## Gemini (com.google.GeminiMacOS) · swiftui
Anchors: button#tempChat_button temporary chat button · button#collapse_button collapse button in toolbar · button#sidebar_toggle sidebar toggle button · button#mic_button microphone / dictation button · button#stc_button speak to window button · button#newNotebookRow new notebook row button · button#notebooks/* notebook entry button (UUID tail is user data)
Quirk unnamed_list_items: address row by its named child button, or by index
Quirk menubutton_no_expand: no Click either: SetFocus then keyboard (Space), or coordinate click after activation
Quirk thumbnail_proxy_window: take bounds from AX root
Quirk offscreen_needs_container_scroll: Scroll sidebar scrollarea, re-snapshot
Quirk enumeration_partial: trust prefix; scroll sidebar scrollarea, re-snapshot
Its window is often hidden: the executor activates it before typing or pointer clicks.
