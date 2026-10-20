## WhatsApp (net.whatsapp.WhatsApp) · catalyst
Anchors: window#SceneWindow main window (root role flips window/dialog) · group#Sidebar_view left navigation rail · button#MediaHub bottom-rail button (labelled Settings in this build) · group#Toolbar chat-list header toolbar · button#NavigationBar_NewChatButton new chat button · textfield#TokenizedSearchBar_TextView chat search field · group#ChatListView_TableView chat list container (Scroll)
Quirk packed_record_value: parse value as record [title, preview, time, status]; name is the last sender, not the chat title
Quirk bidi_salted_text: strip invisible chars before every compare, including app name
Quirk hidden_window_offscreen: read as trusted; activate and re-snapshot before acting
Quirk thumbnail_proxy_window: bounds from AX root (1087x803)
Quirk non_unique_role_name: add index + bounds check
Its window is often hidden: the executor activates it before typing or pointer clicks.
