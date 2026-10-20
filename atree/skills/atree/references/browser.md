# Browser web apps (Safari, Brave, Chrome, Arc)

<!-- provenance: ATree_tool days 2-6, agent-desktop 0.4.0, macOS 15 -->

Browsers natively expose the DOM to the AX tree — one snapshot, no drilling.

- **Navigate via CLI, not UI**: `open "<url>"` (or `open -a Brave "<url>"`).
- **Omnibox**: `Cmd+L` unconditionally focuses + selects the address bar,
  regardless of page state or popups. Pair with `clipboard-set` + `Cmd+V` +
  `Return` for deterministic navigation.
- **Private window**: `Cmd+Shift+N` (Chromium family + Safari) — isolated
  session, clean cache.
- **Load verification**: poll for `role: webarea` plus a target-domain
  statictext before any downstream interaction — `wait --text` does this in
  one call. Never sleep a fixed duration.
- Click targets by name from the tree; coordinate clicks work normally.
- **Canvas/WebGL/video content is out of scope**: playback surfaces expose
  nothing to AX. Do not attempt to verify inside them via the tree.
