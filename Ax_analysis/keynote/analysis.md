# Keynote — AX Tree Analysis

## What was actually captured

Keynote (`com.apple.iWork.Keynote`) was **not running** before the capture (`was_running: false`); it was launched fresh and captured in **background** mode. Consequently the focused window — and the only window with a real tree — is the **"What's New in Keynote" onboarding splash sheet**, not the slide editor, not the theme chooser. Every metric below describes that splash, so this capture is a *lower bound* on Keynote's AX fidelity, not a verdict on the editor canvas.

## Framework evidence

- **Bundle**: `/Applications/Keynote.app`, executable in `Contents/MacOS/Keynote`. No Electron/Qt/Flutter/Catalyst hints.
- **Frameworks list** is the classic iWork stack: `TSKit`, `TSApplication`, `TSDrawables`, `TSText`, `TSTables`, `TSCharts`, `TSStyles`, `TSPersistence`, `KNAnimation`, `EquationKit` — Apple's shared iWork "Tangerine Software" (TS*) C++/Obj-C layer riding on **AppKit**. Notably the bundle ships a dedicated **`TSAccessibility.framework`**, i.e. Apple wrote a bespoke accessibility bridge for the iWork canvas — strong evidence that the document editor (once open) exposes a real, curated AX tree rather than a raster husk.
- **Tree-shape evidence**: the window carries a `native_id` of kind `ax_identifier` with value `_NS:32` — an Interface-Builder-era NSView identifier, i.e. pure AppKit, no webview/webarea anywhere in the tree.

**Verdict on toolkit: native AppKit + Apple's proprietary iWork/TSAccessibility layer.** Not Catalyst, not SwiftUI-dominant, definitely not Electron.

## Measured metrics (full.json, window-scoped)

| Metric | Value |
|---|---|
| Total nodes | 9 |
| Max depth | 3 |
| Named nodes | 3 |
| Interactive nodes (buttons + links) | 6 |
| Interactive with name or value | 3 / 6 (50%) |
| Interactive with bounds | 6 / 6 (100%) |
| Truncated containers (children_count>0, children missing) | 0 (`complete: true`) |
| Nodes exposing available_actions | 7 / 9 |
| Roles histogram | window 1, group 1, scrollarea 1, link 2, button 4 |

- **Actions are rich**: `Click`, `SetFocus`, `RightClick`, `Scroll` appear per-node — semantic AXPress-equivalents are fully exposed.
- **States are readable**: one button correctly reports `disabled`; the window reports `focused`.
- **Values**: one link carries its full visible text in `value` rather than `name` (an AppKit static-text-as-link quirk); no textfields exist on this splash to test value read-back.
- **The 3 unnamed buttons** are the traffic-light close/minimize/zoom controls (12x14 px cluster at the window's top-left) — a cosmetic naming gap in the capture, not an app defect; macOS exposes them with subroles.
- The splash content itself (feature blurbs, imagery) is *not* in the tree — the scrollarea exposes only its two links. The marketing copy is likely drawn, not AX-exposed, which is fine for automation but means a vision pass would see more text than AX does.

## Quirks

- **Ghost windows**: windows.json lists **9** windows, 8 of which are invisible 29–30 px-tall strips titled just "Keynote" (four at x=2560 sized 1280-wide, four full-width at the origin). These are menu-bar/toolbar host husks Keynote materializes at launch — a CUA agent must filter on `visible: true` / `is_focused` or it will target 29-px phantoms.
- **surfaces.json is empty** (`surfaces: []`) — no secondary AX surfaces enumerated at capture time.
- **Background capture was stable**: `complete: true`, zero errors, zero truncation — no husk behavior even without foreground focus. Keynote answers AX queries fully while backgrounded.
- The splash sheet gates the app: any automation session that cold-launches Keynote must first press the well-named, well-actioned **"Continue"** button before reaching the theme chooser / editor.

## What a CUA agent can and cannot do here (pure AX)

**Can**: enumerate the splash reliably in the background; identify and `Click` "Continue" by name (button, `SetFocus` supported); follow either link; read the disabled/enabled state of window controls; get exact bounds for every interactive element as a coordinate fallback.

**Cannot (from this capture)**: judge the slide-editing canvas — no document window was open. Cannot read the splash's marketing copy via AX. Cannot name the traffic-light buttons without subrole inspection.

**Reach strategy**: **semantic-first** — named roles + exposed actions make `find("Continue") → Click` the right loop, with bounds available for coordinate fallback. No CDP (no webview). Keyboard macros (Cmd-N, Cmd-Shift-P, etc.) are a strong secondary channel in iWork. Vision only needed if the future editor canvas hides drawables — though `TSAccessibility.framework` suggests it won't.

## Verdict

This is a small but *clean* native AppKit tree: complete under background capture, 100% bounds coverage, semantic actions on every control, correct states, zero truncation. The only demerits are the unnamed window-chrome buttons and a link whose text lives in `value` instead of `name`. Classified **native-partial** solely because the evidence covers only a 9-node onboarding splash — the toolkit signals (AppKit + a dedicated TSAccessibility framework) predict the full editor will be near native-perfect, but that must be re-captured with a document open. Fidelity from the observed JSON: **8/10** (+1 naming — half the interactives lack a `name`; +2 bounds; +2 values/states; +2 actions; +1 background-stable; +1 no truncation → capped by the naming gap). Recommended next step: dismiss the splash via the "Continue" button and re-snapshot with a presentation open to score the real canvas.
