## Discord (com.hnc.Discord) · electron
Anchors: groupdom#app-mount React app root container · groupdom#popover-portal popover / menu portal layer · tabpaneldom#online-tab friends list tab panel (Online tab)
Quirk volatile_dom_ids: never persist; resolve by role+name under the webarea
Quirk readonly_control_as_button: Click / Expand it; never type into it
Quirk window_id_drift: re-pick window by title + bounds every session; never cache window id
Quirk disabled_keeps_click: check disabled state before acting
Quirk depth_capped_husk: recapture same window at --max-depth 40; no activation, no wait
