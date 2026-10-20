# WhatsApp (macOS) — Accessibility Tree Analysis

**Bundle:** `net.whatsapp.WhatsApp` · **PID at capture:** 26627 · **Capture mode:** `activated` (app was not running; it was launched/activated for the capture)

## What the app is built with

Bundle evidence: the executable is `/Applications/WhatsApp.app/Contents/MacOS/WhatsApp`, and the frameworks folder contains `SharedModules.framework` and `WAAppKitBridge.framework`. No Electron, Qt, Flutter, or Catalyst hints were detected. `WAAppKitBridge` is the telltale: this is WhatsApp's **native AppKit-bridged macOS app** (the modern Swift rewrite that replaced the old Electron/web wrapper).

Tree-shape evidence agrees: no `webarea` node anywhere, a shallow tree (max depth 7), AppKit-style `ax_identifier` native IDs (`SceneWindow`, `Sidebar_view`, `Toolbar`, `NavigationBar_NewChatButton`, `TokenizedSearchBar_TextView`, `ChatListView_TableView`), and semantic actions (`Click`, `RightClick`, `SetValue`, `ScrollTo`) on essentially every node. This is nothing like an Electron husk.

## Metrics (full.json, window-scoped, marked `complete: true`)

| Metric | Value |
|---|---|
| Total nodes | 48 |
| Nodes with names | 29 (60%) |
| Interactive nodes (button/textfield/splitter/link) | 29 |
| Interactive named | 23 (79%) |
| Interactive with bounds | 29 (100%) |
| Nodes with available_actions | 46 (96%) |
| Truncated containers (children_count>0, children missing) | 0 |
| Max depth | 7 |
| Roles | window 1, group 15, button 24, splitter 2, heading 1, textfield 1, statictext 2, link 2 |
| Native ax_identifiers | 7 (all on landmark containers/controls) |

The 6 unnamed interactive nodes are benign: the three window traffic-light buttons (12×14 px at the window's top-left), two 1-px-wide pane splitters (which do carry numeric values and `SetValue`), and one 355×32 px unnamed button that sits directly under the search bar area.

## What the tree exposes

- **The conversation list is fully readable.** The sidebar's chat list (`ChatListView_TableView`) contains ~12 conversation rows exposed as **named buttons**, and each row's `value` attribute carries a rich, screen-reader-grade summary string: sender/contact name, a preview of the last message (sometimes the entire message body), timestamp, delivery/read state ("Sent/Delivered/Read"), group name, and mute/pin status. A CUA agent can triage an inbox without opening a single chat. (Privacy note: these values contain personal names, phone numbers, and full message text — treat every `value` in this app as sensitive user content.)
- **Search is first-class:** a named `textfield` with `ax_identifier: TokenizedSearchBar_TextView` accepting `SetValue` — the anchor for the compiled whatsapp-send route.
- **Navigation chrome is named:** New Chat button (`NavigationBar_NewChatButton`), toolbar, filter buttons, a heading, links, all with real bounds and `Click` actions.
- **Splitters are adjustable** via `SetValue` (values present as proportions).
- **Zero truncation:** every container with children delivers them; the capture self-reports `complete: true`.

What it hides / what was absent at capture time: no chat was open, so the **message compose textfield, message transcript, and send button were not in this snapshot** — they only exist once a conversation is selected. That is view-state, not an AX limitation; prior atree route work confirms they appear as real nodes when a chat is open.

## Background / ghost-window behavior

Two quirks worth flagging:

1. **Ghost window while backgrounded.** `windows.json` shows the sole window as a 130×96 px, partially offscreen (x = −146), `visible: false`, unfocused shell — and the **skeleton** capture (taken against that state) returned a 9-ref husk with every node flagged `offscreen`: bare unnamed groups, splitters, and three unnamed buttons, window `ax_identifier: SceneWindow`. Only after activation did the real 1087×803 window and the 46-ref full tree materialize. So the tree is *not* stable under background capture — you must activate/raise WhatsApp before reading it.
2. **Unicode landmines in names.** The app name, window title, and most values are salted with invisible bidi control characters (U+200E LEFT-TO-RIGHT MARK, U+202F narrow no-break space). Exact-string matching on "WhatsApp" or on row values will fail; matchers must strip/normalize these (the app is literally named `‎WhatsApp` in AX).
3. `surfaces.json` lists zero surfaces — no auxiliary sheets/popovers at capture time.

## What a CUA agent can and cannot do via pure AX

**Can:** enumerate and read the entire chat list (names, previews, unread/mute/pin state) without clicks; click any conversation row (`Click` on the row button); set the search field directly with `SetValue` and navigate results; hit New Chat, filters, toolbar buttons; right-click rows for context menus; resize panes. Once a chat is open (per the verified `route-whatsapp-send` skill), type into the compose field and send — a full semantic loop.

**Cannot / caution:** read anything while the app is backgrounded (husk); rely on raw string equality (bidi marks); read the compose/transcript region from this snapshot alone (requires opening a chat first); the three traffic-light buttons and one search-adjacent button are unnamed, so target those by `native_id`/geometry, not name.

## Reach strategy

**Semantic-first, unconditionally.** Anchor on `ax_identifier`s (`TokenizedSearchBar_TextView`, `NavigationBar_NewChatButton`, `ChatListView_TableView`) which are stable across sessions, use `SetValue` on the search field, `Click` on named rows, and keyboard (Return) to commit. No need for coordinates, CDP (not a web app), or vision. Preconditions: activate the app first and normalize Unicode in all name/value comparisons.

## Verdict

WhatsApp's native macOS client is one of the better AX citizens among messaging apps: a compact, fully-bounded, action-rich AppKit tree with stable developer-assigned identifiers and unusually generous row values that expose whole message previews to assistive tech. Its only real sins are the offscreen husk it presents when backgrounded (activation is mandatory before capture) and the invisible bidi characters peppered through every name and value. Score **8/10, native-partial** — a point and a half short of perfect only for the handful of unnamed chrome buttons and the background-husk instability; with the app frontmost, a pure-AX agent can run the complete find-contact → open-chat → compose → send loop with no pixel work at all.
