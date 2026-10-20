# Telegram (macOS) — Accessibility Tree Analysis

**Bundle:** `ru.keepcoder.Telegram` (`/Applications/Telegram.app`) · **PID** 26876 · **Capture mode:** background (`was_running: false` — the app was cold-launched for this capture)

## What the app is built with

Bundle evidence is unambiguous: this is the **native Swift Telegram client ("Telegram for macOS" / TelegramSwift)**, not the Qt-based Telegram Desktop and not Electron. The frameworks list is a wall of `libswift*` dylibs (`libswiftAppKit`, `libswiftMetal`/`MetalKit`, `libswiftSceneKit`, `libswiftVision`, …) with **zero** Electron/Qt/Flutter/Catalyst hints. The UI is Swift/AppKit with heavy custom Metal/CoreGraphics rendering — Telegram famously draws most of its chat UI itself rather than composing standard AppKit controls.

Tree-shape evidence is consistent with that: the one node we did get is a genuine AppKit `window` carrying an NIB-style `ax_identifier` (`_NS:13`), i.e. a real Cocoa window, not a webarea husk.

## What this capture actually got

Essentially nothing below the window:

| Metric | Value |
|---|---|
| Total nodes (full.json) | **1** (the focused window only) |
| Named nodes | 1 (the window, name "Telegram") |
| Interactive elements exposed | **0** |
| Truncated containers | 1 (the window root, `subtree_truncated: true`) |
| Max depth | 1 |
| Values / states / actions | none observed |
| Windows enumerated | 9 |

- `skeleton.json` and `full.json` are both a single truncated window node (`complete: false`, `nodes_observed: 1`). full.json adds bounds on the window; nothing else differs.
- `surfaces.json` failed outright with `APP_UNRESPONSIVE`: the `AXChildren` array on some surface reported **56 children but 0 could be loaded** (`surface_array_incomplete`, count unchanged across the read). The AX server inside the app never materialized its children while backgrounded.
- `windows.json` shows classic **ghost windows**: 9 windows total, of which only one (1087x803, focused) is real. The other 8 are invisible 29–30 px tall strips — four parked off-screen at x=2560 and four full-width 2560x30 bars at the top of the display (menu-bar/overlay/title-bar helper windows). A naive "pick the first window" strategy would target a ghost; window selection must filter on `visible` + plausible bounds.

## Interpretation: husk under background capture

This is the signature of an app whose AX subtree is **lazily populated on the main thread and only when the app is active/foreground**. Cold-launched into the background, Telegram's custom-drawn Swift UI answered the window-level attributes but stalled every `AXChildren` fetch (56 promised, 0 delivered). The result is a husk — structurally similar to an Electron veil, but the cause is a busy/deferred native AX implementation, not a webarea wrapper. `husk_on_background = true` on the evidence of this capture.

Important caveat: this capture **cannot distinguish** "Telegram never exposes a usable tree" from "Telegram exposes nothing while backgrounded/cold-starting." The 56-child count that the AX server *advertised* suggests real structure exists behind the stall. Known behavior of TelegramSwift is a partially custom AX tree (rows in the chat list often exist as elements but with patchy names/roles because everything is custom-drawn). A foreground re-capture after the app finishes launching is required before trusting any score higher than what's below.

## Fidelity score (from this JSON evidence only)

- All interactive elements present & named: **0/2** (zero interactive nodes)
- Bounds on interactive elements: **0/2** (none exist; only the window has bounds)
- Values/states readable: **0/2**
- Semantic actions exposed: **0/2**
- Stable under background capture: **0/1** (this is the defining failure — APP_UNRESPONSIVE husk)
- No truncated containers: **0/1** (the root itself is truncated)

**Score: 0/10** for this capture. **Category: opaque-none** — no usable tree was obtained. (The app itself is likely native-partial when foregrounded and warm; that classification must be earned by a re-capture, not assumed.)

## What a CUA agent can / cannot do here via pure AX

**Can (from this capture):** find the real window (filter ghosts by `visible` and sane bounds), read its title/bounds/focus state, raise it.

**Cannot:** see the conversation list, message input, send button, search field, or any content; read any value; press anything semantically. There is literally nothing to target below the window.

## Reach strategy

1. **First remedy: activate + retry.** Bring Telegram to the foreground, wait for launch to settle (the `was_running: false` cold start is a confound), and re-snapshot. Expect the 56 advertised children to materialize; then re-grade.
2. **If the foreground tree is real but patchy** (typical for custom-drawn Swift UIs): **semantic where possible, keyboard macros as the workhorse.** Telegram has strong keyboard affordances — Cmd+F / search field to reach any chat by typed name, Enter to open, type-and-Enter to send — which sidesteps unnamed custom cells entirely.
3. **If the tree stays a husk even foregrounded:** fall back to **coordinate + vision** (screenshot-grounded clicks). CDP is not applicable — this is not a web runtime.
4. Never automate this app in background mode; every read risks `APP_UNRESPONSIVE` timeouts that stall the whole capture pipeline.

## Notable quirks

- **Ghost-window swarm:** 8 invisible helper windows (off-screen strips and full-width 30 px bars) around 1 real window; window pickers must filter.
- **Advertised-but-unloadable children:** AX reports `total_count: 56` on a surface while delivering 0 — treat child-count claims from this app as promises, not facts.
- **Cold-start confound:** the capture launched the app (`was_running: false`); part of the emptiness may be launch-time, not steady-state.
- Custom Metal-rendered UI means even a healthy foreground tree will likely have unicode-decorated, user-content-derived names on list cells (emoji, RTL text) — matchers should normalize.

## Verdict

Telegram for macOS is a fully native Swift/AppKit app (no Electron/Qt), but under a background cold-start capture it presented as **opaque**: a single truncated window node, an `APP_UNRESPONSIVE` surface enumeration that promised 56 children and delivered none, and a swarm of eight ghost windows around the one real one. Score 0/10 **for this capture** — the honest reading is not "Telegram has no AX tree" but "Telegram's AX tree is unreachable while backgrounded/cold." The prescribed next step for any CUA route is foreground activation with a settle-wait and a re-snapshot; until then, plan around keyboard-macro navigation (search-driven) with vision/coordinate fallback, and never rely on background AX reads for this app.
