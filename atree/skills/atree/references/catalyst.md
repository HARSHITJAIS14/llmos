# Native / Catalyst apps (Finder, Safari, Calendar, WhatsApp)

<!-- provenance: ATree_tool days 1-4, agent-desktop 0.4.0, macOS 15 -->

Full AX integration: ONE snapshot captures everything. No drill-downs.
Semantic `click <ref>` (AXPress) works reliably — and works in the
background without stealing focus. Prefer it over coordinates here.

## Per-app quirks
- **Finder**: several windows all named "Finder" — pick the one with a real
  title, pass `--window-id`.
- **WhatsApp (Catalyst)**: does NOT appear in `list-windows --app WhatsApp`.
  Use global `list-windows` and filter titles containing "WhatsApp".
- **Calendar**: background extension processes cause global `list-windows`
  timeouts. Scope directly: `snapshot --surface popover` / `--surface focused`
  for Quick Event UI (`QuickEventNewEventButton`, `QuickEventCell`).
- **Role drift in lists**: contacts/search results flip between `button`,
  `cell`, `statictext` across captures. Match on several likely roles.

## Focus management (physical input only)
Physical keystrokes/clicks can leak into the terminal running the agent.
Before EVERY typing sequence or physical click:
`osascript -e 'tell application "X" to reopen' -e 'tell application "X" to activate'`
(`reopen` recreates a closed main window; `focus-window` alone fails on
ghost/opaque windows).
**Exception**: never activate before semantic `click <ref>` — it works in the
background and activating steals the user's focus for nothing.
