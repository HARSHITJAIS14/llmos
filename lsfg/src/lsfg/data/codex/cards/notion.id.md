## Notion (notion.id) · electron
Anchors: groupdom#root renderer root container · groupdom#notion-app app root container · maindom#main page content region · linkdom#skip-to-content skip to content link · radiobuttondom#sidebar-tab-home sidebar home tab · radiobuttondom#sidebar-tab-chats sidebar chats tab · radiobuttondom#sidebar-tab-meetings sidebar meetings tab · radiobuttondom#sidebar-tab-inbox sidebar inbox tab · tabpaneldom#sidebar-tabpanel-home sidebar home tab panel
Quirk volatile_dom_ids: never persist these ids; resolve by role+name+nth instead
Quirk zero_area_clones: drop zero-area nodes before resolution; never click them
Quirk non_unique_role_name: use nth index plus bounds check; multi-match is an error
Quirk document_as_single_value: read value and split lines; type at a known caret, avoid SetValue on the whole page
Quirk readonly_control_as_button: Click/Expand it to open its menu; never type into it
