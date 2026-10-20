# App archetype index

Classify the target app FIRST, then load ONLY that reference file. This index
is the whole always-on budget; everything below it is loaded on demand.

| Archetype | Signs | Examples | Load |
|---|---|---|---|
| **native** | full AX tree in one snapshot | Finder, Safari, Calendar, WhatsApp (Catalyst) | `catalyst.md` |
| **electron** | tree truncated behind a webarea; ghost windows | Notion, VSCode, Slack, Discord | `electron.md` |
| **qt-opaque** | full hierarchy but `bounds: None` | OBS Studio, many Qt apps | `qt-opaque.md` |
| **browser-web** | target is a website in a browser | YT Music in Safari, any web app | `browser.md` |

Cross-cutting references (load when the situation arises, not upfront):
`dialogs.md` (save/open sheets, Cmd+Shift+G) · `rich-text.md` (formatted paste)

Unknown app? One `agent-desktop snapshot --skeleton --app "X" -i --compact`
tells you: full tree = native; truncated webarea = electron; no bounds = qt-opaque.
