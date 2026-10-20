# Structurally transparent, spatially opaque apps (OBS, Qt)

<!-- provenance: ATree_tool day 3, OBS Studio, agent-desktop 0.4.0, macOS 15 -->

Full hierarchical UI exposed to the AX tree, but `bounds: None` on
everything — the OS does not know WHERE any control is.

- Physical `mouse-click --xy` is impossible: there are no coordinates.
- The ONLY path: query the ephemeral `ref_id`, dispatch semantic
  `agent-desktop click <ref>` (AXPress). The OS routes the press in memory.
- This works fully in the background — never activate the app first.
- Verification: bounds-based vision rungs are unavailable (no bounds).
  Verify via AX state only: re-query the control's `value`/`states`
  (e.g. OBS "Stop Recording" button appearing is the postcondition for
  "recording started").
