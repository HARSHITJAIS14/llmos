---
name: atree
description: >
  macOS desktop automation via the accessibility tree using agent-desktop.
  Use for any request to observe, click, type into, or automate a native Mac
  application (open apps, send messages, fill dialogs, toggle settings, drive
  Notion/VSCode/Finder/Calendar/OBS/browsers). Provides the `ax` command:
  recall -> observe (diff-tracked) -> find -> do (declare+act+verify in one
  call). Triggers on: "click", "open app", "automate", "desktop",
  "send message", "accessibility tree", "agent-desktop".
---

# atree: drive macOS through `ax`

## Speed: match the ceremony to the task

- **Trivial task** (ONE obvious action — a keystroke, one click on a named
  element, pasting text — with an obvious postcondition): go STRAIGHT to
  `ax do` / `ax type`. No recall, no observe. One tool call, done.
- **Familiar app, simple task**: `ax recall` first — an L1 hit replays in one
  call; L2 gives you coordinates without observing.
- **Unfamiliar app or multi-step task**: the full loop below. This is where
  the ceremony pays for itself.

Batch independent shell steps into one call where you can; every extra turn
costs seconds of round-trip.

Four commands run the whole loop. Use them instead of raw `agent-desktop`
invocations — they handle ghost windows, Electron drill-down, state diffs,
verification, and registry deposits automatically.

```bash
ax recall  "<task>" "<App>"     # ALWAYS FIRST. L1: replay steps. L2: known elements. miss: discover.
ax observe "<App>"              # perceive: compact digest of interactive elements (first look)
                                #           or a diff of what changed (every later look)
ax find    "<App>" "<text>"     # locate a click/type target: role, name, ref, center coords
ax open    "<App>"              # launch/activate an app, verified frontmost (NEVER Spotlight/Dock)
ax type    "<App>" "<text>"     # enter text: atomic clipboard paste (restores user clipboard)
ax do '<postcondition-json>' -- <action...>   # declare + act + verify, atomically
```

`ax do` examples — the postcondition is what the action MUST make true;
it is checked against fresh AX state and the command exits 2 with a
diagnosis if the action didn't land:

```bash
# semantic click (background-safe, preferred for native/Qt apps)
ax do '{"kind":"title_matches","expect":{"pattern":"cursor for che"},"app":"Notion","description":"page opened"}' \
  -- click @s3abc:e42

# physical click (Electron apps; ax activates the app first automatically)
ax do '{"kind":"title_matches","expect":{"pattern":"cursor for che"},"app":"Notion"}' \
  -- mouse-click --xy 295,647

# keystroke + value check
ax do '{"kind":"value_contains","expect":{"role":"textfield","value":"youtube.com"},"app":"Safari"}' \
  -- press cmd+l
```

Postcondition kinds: `node_exists`, `node_absent`, `value_equals`,
`value_contains`, `title_matches` (expect `{"pattern": ...}`; a literal
`{"title": ...}` also works). Selectors: `role`, `name`, `name_contains`,
`native_id`.

## Hard rules

1. **NEVER screenshot to find or verify an element.** `ax find` gives you the
   name, ref, and click coordinates from the AX tree. Screenshots are the LAST
   diagnosis rung (after `ax observe` and `python3 -m core.vision`), only when
   AX and reality disagree, and always cropped — never as your eyes.
2. **Never act without a postcondition.** Every mutating step goes through
   `ax do`. A raw `agent-desktop click/press/type` with no declared
   postcondition is a bug.
3. **No fixed sleeps.** `agent-desktop wait --element/--text/--window/--event`
   are predicates; `ax do` already polls the postcondition up to `timeout_ms`.
4. **One atomic action per step.** Observe -> act -> the verdict tells you it
   landed. Do not chain three clicks on hope.
4a. **Apps open via `ax open`, never Spotlight/Dock/UI.** osascript
   reopen+activate launches, restores, and focuses in one verified call.
4b. **Text goes in via `ax type`, never per-character keys.** Clipboard paste
   is one atomic call for any length, generates real input events (Electron/
   React registers it — semantic `set-value` often doesn't), and restores the
   user's clipboard. Focus the field first, then `ax type`.
5. If `ax observe` says the window is on a non-active Space, activate the app
   (it prints the exact command), then re-observe.

## Archetype knowledge

Classify the app FIRST via `references/archetypes.md`, load ONLY that one
file: `electron.md` (Notion/VSCode: keyboard macros beat clicks; AXPress is
swallowed), `catalyst.md` (Finder/WhatsApp/Calendar: one snapshot, semantic
clicks, focus rules), `qt-opaque.md` (OBS: no bounds — semantic only),
`browser.md` (navigate by URL, Cmd+L). Dialogs/rich text: `dialogs.md`,
`rich-text.md`. CLI flags and traps: `agent-desktop-cli.md`.

## Safety invariants (non-negotiable)

- **Recipient verification**: before typing into any message field,
  postcondition the chat header == target recipient (`node_exists` with
  `name_contains` scoped to the header). Mismatch = halt.
- **Disambiguation**: multiple candidates for a target -> STOP and ask the
  user. Never `results[0]`.
- **Denylisted apps** (Messages, password managers, banking): no exploration,
  no deposits; act only on an explicit user instruction for that action.

## After the task

Worked end-to-end twice? Compile it: `skills/atree-learn` (route command +
`registry.save_route` so recall returns L1 next time). Discovered a quirk
verification confirmed? It is already in `~/.atree/state/outcomes.jsonl`;
`/ax-learn` promotes what the evidence supports.
