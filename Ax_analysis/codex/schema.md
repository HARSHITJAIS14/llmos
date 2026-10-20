# atree codex: per-app file format

One JSON file per app, `apps/<app_key>.json`, checked against `schema.json` (JSON Schema 2020-12).
Three readers use these files: the dispatcher (picks a capture plan), the route compiler (builds selectors), and a small local model (reads the enums). Because of that, every enum is closed and no field holds free-form personal text.

**Privacy rule:** no names, messages, emails or file names anywhere. Anchors store only generic ids (or the non-personal prefix of an id). `purpose` and `observed` describe UI function and counts only.

**Law ids.** `LAW-WIN/ACT/ID/TXT/STR-n` are in `laws.md`. `LAW-LIFE-1..12` are the 12 entries of `lifecycle_laws.json`, in file order:
1 husk comes from the depth cap · 2 husk predicate · 3 Chromium 7-node fingerprint · 4 native background trust · 5 offscreen = hidden window · 6 bounds/root role are per-snapshot · 7 partial prefix is stable · 8 Telegram opaque · 9 RefMap overflow · 10 window/process target errors · 11 launch transient · 12 readiness ladder.

---

## Top-level fields

| Field | What it holds | Laws |
|---|---|---|
| `schema_version` | Always `"1.0"`. | - |
| `app_key` | Directory name, e.g. `google_chrome`. | - |
| `identity` | Name, bundle id, framework, and the evidence for that framework. | STR-1, STR-5, ACT-13, LIFE-3 |
| `category` | What kind of app it is (browser, messaging, ...). | - |
| `fidelity` | Default vs forced capture numbers, scores, and the ladder verdict. | LIFE-1, LIFE-2, LIFE-12 |
| `readiness` | Husk behavior, capture plan, activation needs, handshake, settle times. | LIFE-1..4, 7, 11, 12 |
| `window_picking` | Ghost geometries seen for this app and the real-window test. | WIN-1..10, LIFE-10 |
| `selector_strategy` | Ordered resolver chain plus app specifics (value identity, bidi cleanup). | ID-1..12 |
| `stable_anchors` | `native_id`s worth saving, each with kind, tier, role and purpose. | ID-1..3 |
| `action_capability` | Which actions mean what here, per role. | ACT-1..12 |
| `read_recipes` | Where readable text lives, per kind of node. | TXT-1..12 |
| `verify_recipes` | How to check that an action worked. | TXT-1, TXT-7, TXT-8, ID-8, ID-11 |
| `geometry` | Whether bounds can be trusted and when they go stale. | WIN-3..5, LIFE-5, LIFE-6, ID-7 |
| `quirks` | Known traps, each typed with a closed `kind`, a detection test and a workaround. | see table below |
| `escalation` | Channels to try, in order: AX -> handshake -> CDP -> keyboard -> vision. | LIFE-8, LIFE-9, LIFE-12, TXT-8 |
| `provenance` | Capture dates, tool version, app version, which surface was captured. | STR-12 |

---

## Field notes

### identity
- `framework`: one of `appkit, swiftui, catalyst, iwork, webkit_native, wkwebview_webapp, electron, chromium_browser, gecko, qt, cef, custom_cpp, unknown`. This is the main key the dispatcher switches on.
- `secondary_frameworks`: embedded engines (OBS = `qt` + `cef`).
- `framework_evidence[]`: each item is `{source, observation}`. Sources: bundle frameworks (from `meta.json` framework_signals), bundle hint, skeleton fingerprint (7 nodes + 4 root kids = Chromium shell, LIFE-3), root-to-webarea path (STR-1), noise ratio (STR-5), role histogram (ACT-13), wrapper chain length (STR-4), depth band (STR-3). The observation must include the number.
- `bundle_id_match: prefix` covers Safari web apps, whose bundle id ends in a per-install UUID (YT Music).

### fidelity
- `default` / `forced`: the same `capture_stats` block. `frontier_nodes` counts nodes where `children_count > len(children)`. That is the real depth-cap signal, because `complete=true` can still hide a depth cap (STR-6).
- `forced_over_default_ratio`: 1.3 or more means the default capture was untrustworthy. The corpus has a clean gap: the highest trustworthy app was 1.05 (LIFE-2).
- `default_score` = default nodes / most nodes ever seen for that window. 1.0 means the cheap capture is enough.
- `ladder_verdict`: `trust | recapture_deeper | navigate_partial | activate_first | refmap_split | give_up` (LIFE-12).

### readiness
- `default_rung`: the first rung of the readiness ladder that the default capture hit (`TRUST`, `R2_opaque`, `R3_unsettled`, `R4_depth_frontier`, `R5_partial_prefix`, `R6_hidden_window`, `E_refmap`, `E_window`).
- `husk.signals`: which parts of `untrusted(snapshot)` fired. `husk.cause`: `depth_cap` for all 8 web stacks, `opaque` for Telegram, `launch_transient` for Keynote, `size_limit` for Antigravity (LIFE-1, 2, 8, 9, 11).
- `capture_plan.max_depth`: 10 for native (never deeper than 9 in the corpus, STR-3), 40 for web (LIFE-3). `scoped_drill` means capturing with `snapshot --root` per frontier ref (RefMap case). `drill_truncation_boundary` is always false, because 0 of 7 drills worked (LIFE-7).
- `background_read_ok`: native apps can be read without activation. Activation added 0-5% of nodes and changed 0% of text (LIFE-4).
- `needs_activation.act`: true when the window is usually hidden. Coordinates are only safe after activating (LIFE-5).
- `handshake.status`: `unproven` for web stacks, because depth explains all the data. `tool_automatic` means agent-desktop sends it by itself. `not_applicable` for native apps (LIFE-1, LIFE-12).
- `settle_ms`: only the launch case needs a wait. After launch, re-list windows about 2s apart and continue once the window id is stable and n > 12 (LIFE-11).

### window_picking
- `ghost_signatures[]`: fake window-server entries seen for this app (`menubar_strip` 2560x30 / 1280x29, `helper_surface` 0x0 / 1x1 / 64x64 / 500x500, `thumbnail_proxy` <= 200px, `sliver` such as the TextEdit 678x64) (WIN-1, 2, 4, 9, LIFE-10).
- `real_window_test`: must be > 200px, bounds must match the AX root exactly, and n must be > 12. A title that differs from the app name proves the window is real (WIN-5, 7, LIFE-11).
- `empty_list_is_normal`: Finder, Firefox, WhatsApp. Every entry was a ghost but AX still had the window, so snapshot anyway (WIN-10).
- `address_by`: use `window_id` by default. Never use `--app` when several processes share the name (Firefox had 11) (LIFE-10).
- `window_id_drifts`: the window id changed between captures (Keynote, Zoom, Chrome), so re-pick the window every session.

### selector_strategy
- `chain`: resolver tiers tried in order, from `native_id, role_name_nth, textfield_value, value_prefix, ancestor_path`. `ref_id` is never stored; it is only valid inside one snapshot (ID-8, ID-12).
- `search_root: webarea` for Electron. The Electron shell outside the webarea is about 10-12 nodes (STR-2).
- `normalize.strip_invisible`: remove bidi and zero-width characters. This is always safe. It matters for WhatsApp (57 chars), Word (18) and Safari (4) (ID-10).
- `identity_field: value` for AppKit list labels, which live in `textfield.value` with no name (ID-4).
- `native_id.reject_patterns`: volatile ids such as React `:r..:` and `view_<n>` (ID-3).
- `uniqueness`: (role, name) is unique for only 68% of named interactives; adding bounds brings that to 98%. `nth_required_roles` lists the roles that always need an index (ID-6).
- `on_multi_match` is always `error` (ID-7). `view_change_overlap`: below 0.6, abort; above 0.9, reuse (ID-11).

### stable_anchors
Each anchor is `{kind, value, match, tier, role, purpose}`.
- `tier`: `high` (hand-written path, safe to persist; OBS, Safari, Calendar), `session` (contains a UUID, so re-resolve each launch), `low` (`_NS:<n>`, valid for this build only).
- `match: prefix`: use when the tail of the id is user data (Calendar ids carry a calendar title). Store only the prefix (ID-2).
- Keep at most 60 anchors, chosen for route value, not completeness.

### action_capability
- `click_is_signal`: false only for Gecko (97% of non-interactive nodes have Click) (ACT-5).
- `rightclick_ambient`: true for web stacks (ACT-6).
- `disabled_keeps_click`: true almost everywhere, so check the `disabled` state instead. False in WebKit-native and Qt (ACT-7).
- `editable_textfield_test`: `setfocus_present` for AppKit/iWork, where a textfield without SetFocus is a label (ACT-8). `typetext_present` for web stacks (ACT-9).
- `offscreen_recovery`: `scroll_to` for web, `container_scroll` for AppKit (0/3181 had ScrollTo), `leaf_scroll` for Catalyst (ACT-11).
- `roles[]`: `{role, actions, count, verb}` for roles that carry a real action in this app. `verb` is the action to use (Toggle for checkbox/radio/switch per ACT-2; Select only on containers per ACT-4).

### read_recipes
- `tree_readable`: `full`, `partial` (complete=false prefix), `write_only` (Gemini: a composer exists but the content region has almost no text, TXT-8), or `opaque` (Telegram).
- `recipes[]`: `{target, match, read_from, parse}`. Examples: statictext -> `name_or_value` (TXT-2); list item label -> `value` (TXT-3); cell/row -> `children_join` (TXT-4); heading -> `name`, and its value is the level (TXT-6); toggle -> `value` + `bool_01` (TXT-10); document body -> `value` + `split_lines` (TXT-12); WhatsApp chat row -> `value` + `comma_record` (TXT-5).

### verify_recipes
- `after_type: value_key_equals`: the value key must appear and equal the typed text. An empty field has no value key at all (TXT-1).
- `never_compare_name` and `resnapshot_after_action` are always true (TXT-7, ID-8).
- `channel: vision` or `tree_then_vision` for write-only or opaque apps (TXT-8, LIFE-8).

### geometry
- `bounds_source: ax_root` when window-server bounds are a thumbnail or don't match exactly. There is no "slightly off" case (WIN-4, WIN-5).
- `stable_across_activation`: false for Notes, TextEdit, Reminders and Word (0% of bounds kept). true for Safari, VLC, Calendar and UTM (LIFE-6).
- `invalidate_on`: always includes `activate`. `root_role_varies`: root flips between window and dialog; treat both as the same (LIFE-6).
- `offscreen_click` is always `forbidden` (ACT-11). `zero_area_nodes` are never clicked (ID-7, LIFE-3).

### escalation
Ordered list of `{channel, when, precondition, tested}`. Channels, in order: `ax -> ax_deep -> ax_scoped -> handshake -> cdp -> app_api -> keyboard -> vision`. List only the channels that apply. `tested: false` marks untested steps: CDP was never run, and the Antigravity scoped drill is only inferred (LIFE-9).

### provenance
- `app_version` is `null` for the whole 2026-08 corpus, because it was not recorded. Record it next time.
- `surface`: which screen the captures show (`main`, `sign_in`, `splash`, `start_page`, `open_panel`, `idle`, `unknown`). This matters because most apps were captured once: Keynote was a splash screen, Claude a sign-in page, and Safari the Start Page.
- `excluded_sources`: e.g. `music/forced.json` (it is really YT Music, STR-12).
- `verified`: false until an adversarial verify pass runs.

---

## Quirk enum (closed, 32 kinds, each one seen in the corpus)

| kind | Seen in | Detect (short) | Workaround | Laws |
|---|---|---|---|---|
| `depth_capped_husk` | Discord, Notion, Claude, Brave, Chrome, Firefox, YT Music, Antigravity | webarea + a node with children_count > len(children), or max depth == cap | recapture at depth 40, no activation | STR-6, LIFE-1..3 |
| `opaque_root` | Telegram | n==1, root subtree_truncated, ref_count==0 | give up on AX at once | STR-8, LIFE-8 |
| `enumeration_partial` | Finder, Safari, Reminders, Gemini, Keynote | complete=false, nodes_observed > n | trust the prefix, scroll or search | STR-7, LIFE-7 |
| `silent_enumeration_loss` | Safari, Gemini | complete=false with no subtree_truncated marker | same as above; can't locate the loss | STR-7 |
| `drill_timeout` | Keynote, Reminders | snapshot --root returns TIMEOUT | never drill; scroll instead | LIFE-7 |
| `refmap_overflow` | Antigravity | error INTERNAL containing "RefMap" | scoped drill per frontier ref | LIFE-9 |
| `launch_transient_window` | Keynote | n <= 12 right after launch | re-list, activate, recapture once | LIFE-11 |
| `window_id_drift` | Keynote, Zoom, Chrome | best window id differs between captures | re-pick window per session | LIFE-11 |
| `thumbnail_proxy_window` | Antigravity, Firefox, Safari, Brave, VLC, YT Music | only visible entry is <= 200px | use title only, bounds from AX root | WIN-4 |
| `ghost_only_window_list` | Finder, Firefox, WhatsApp | every WS entry is a ghost | snapshot anyway | WIN-10 |
| `hidden_window_offscreen` | Safari, VLC, WhatsApp | root offscreen, or >= 90% offscreen with complete | read OK; activate before acting | LIFE-5 |
| `ambiguous_process` | Firefox | AMBIGUOUS_TARGET, candidate_count > 1 | address by pid / window-id | LIFE-10 |
| `textfield_is_label` | Finder, Keynote | AppKit textfield without SetFocus | treat as statictext; never SetValue | ACT-8 |
| `identity_in_value` | Finder, Keynote, TextEdit | textfield with value, no name | resolve by value | ID-4, TXT-3 |
| `bidi_salted_text` | WhatsApp, Word, Safari | invisible format chars in name/value | strip before every compare | ID-10 |
| `volatile_dom_ids` | Notion, Discord, Claude | id matches React useId / view_<n> | never persist those ids | ID-3 |
| `user_data_in_id` | Safari, Calendar | id holds a UUID or user title | prefix match, tier session | ID-2 |
| `click_everywhere` | Firefox | Click on statictext/toolbars | filter by role, not by Click | ACT-5 |
| `disabled_keeps_click` | AppKit, Chromium, Electron, Gecko apps | disabled state + Click present | check the disabled state | ACT-7 |
| `mass_focused` | Finder, Keynote | more than 3 focused nodes | real focus = the focused container | ACT-10 |
| `offscreen_needs_container_scroll` | Finder and other AppKit apps | offscreen node without ScrollTo | scroll the nearest scrollarea | ACT-11 |
| `menubutton_no_expand` | WhatsApp, Word | menubutton without Expand | use Click | ACT-3 |
| `unknown_role_actionable` | Zoom | role unknown with Click | treat as button | ACT-12 |
| `readonly_control_as_button` | Notion, Zoom, Reminders | readonly combobox/textfield | Click it; never type into it | TXT-11 |
| `non_unique_role_name` | Calendar, YT Music, Notion | (role,name) unique < 70% | index + bounds check | ID-6 |
| `zero_area_clones` | Notion | width or height == 0 duplicates | drop them from resolution | ID-7 |
| `unnamed_list_items` | Gemini, OBS | rows/cells with no name | address by index or named child | ID-5 |
| `write_only_surface` | Gemini | TypeText present, content text < 50 chars | verify with vision | TXT-8 |
| `packed_record_value` | WhatsApp | button.value is a comma-joined record | parse as a record; name is not the title | TXT-5 |
| `document_as_single_value` | Notion | one unnamed textfield holds the whole page | read value, split lines | TXT-12 |
| `toggle_value_is_label` | AppKit tab-style radiobuttons | radiobutton value == label text | read as text, not as state | TXT-10 |
| `embedded_file_browser` | Keynote (open panel) | role `browser` at depth ~3 | drive it like Finder | STR-11 |

Rules that apply to every app (ref_id is snapshot-scoped, key absence means empty, heading value is the level, window/dialog root flip) are not quirks. They are fixed in the schema as constants (`on_multi_match`, `never_compare_name`, `offscreen_click`, `drill_truncation_boundary`).

A new quirk needs a schema bump. It must have been seen in a capture before it can be added to the enum.
