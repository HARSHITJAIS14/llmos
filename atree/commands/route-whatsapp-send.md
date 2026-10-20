---
description: Send a WhatsApp message to a contact (compiled route, verified)
argument-hint: <contact name> | <message>
---

Send a WhatsApp message. Parse $ARGUMENTS as `<contact> | <message>`.
Compiled from the verified ATree_tool task; every step declares its
postcondition (the verify hook enforces them), no fixed sleeps.

1. **Focus** (physical input follows — catalyst.md focus rule):
   `osascript -e 'tell application "WhatsApp" to reopen' -e 'tell application "WhatsApp" to activate'`
   WhatsApp is Catalyst: it will NOT appear in `list-windows --app` — use the
   global list filtered by title if a window id is needed.
2. **Search**: declare postcondition `node_exists {role: textfield}` scoped to
   the search area, then `agent-desktop press cmd+f`, type the contact name.
3. **Open chat**: candidates may be `button`, `cell`, or `statictext` — match
   all three roles. **If more than one contact matches, STOP and ask the user
   which one** (AskUserQuestion) — never take results[0].
4. **RECIPIENT VERIFICATION (hard gate)**: declare postcondition
   `node_exists {name_contains: "<contact>"}` scoped to the chat header
   BEFORE any typing. On mismatch: halt with RECIPIENT_MISMATCH. This is the
   safety invariant; it is not skippable.
5. **Send**: `clipboard-set "<message>"`, focus the message field, `press
   cmd+v`, then `press return`, with postcondition `value_equals` on the (now
   empty) message field plus `node_exists` for the sent message text in the
   transcript region.
6. Report: recipient verified as, message sent, turns used.
