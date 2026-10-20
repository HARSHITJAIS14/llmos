## Claude (com.anthropic.claudefordesktop) · electron
Anchors: groupdom#root web app root container (one per webarea) · groupdom#portal-root overlay/portal container (zero height when empty)
Quirk depth_capped_husk: recapture same window at --max-depth 40, no activation
Quirk volatile_dom_ids: never persist React useId values; anchor on root/portal-root or role+name
Quirk window_id_drift: re-pick window each session; never cache window id
