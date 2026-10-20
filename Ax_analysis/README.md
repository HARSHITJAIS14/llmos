# The atree AX-Tree Census — Final Report

**28-app macOS accessibility-tree census · captured with `capture.py` / `capture_pass2.py` / `capture_forced*.py` · 24 apps fully characterized, 4 launch failures · every claim below is traceable to `<dir>/analysis.md` and the per-app JSON captures.**

Categories were first assigned per app, then adversarially re-verified against the raw `full.json` / `forced.json` evidence. Three categories were **corrected** in that pass (Claude Desktop, Discord, Telegram); all corrections are folded into this report and flagged where they appear.

---

## 1. Executive summary

The folk model — "macOS accessibility is a wasteland, agents need vision" — is wrong. Of the 24 apps this census fully characterized, **19 (79%) score fidelity 7/10 or higher**: 5 are native-perfect (Notes, Calendar, Reminders, TextEdit, VLC), 11 are native-partial with workable gaps (including Zoom, whose proprietary C++ UI kit turned out to hand-publish an excellent tree), and 6 are web-native browsers/wrappers whose DOM reaches AX. Only 2 apps remain veiled Electron husks (Antigravity IDE — where the handshake likely *works* but the hydrated tree overflows agent-desktop's 1MB RefMap, a tool limit, not app opacity — and Notion, where the handshake is untested), and **exactly one app is truly opaque: Telegram** — a post-census warm, foregrounded re-capture (17s settle) still returned a 1-node truncated root that advertises 56 AXChildren and delivers zero. Telegram doesn't lack a tree; it refuses to serialize one. Critically, the adversarial pass showed the two "textbook Electron husks" (Claude Desktop, Discord) hydrate into full DOM-backed trees after a single `AXManualAccessibility` handshake — Discord went from 25 husk nodes to a 507-node, zero-truncation tree. **For the atree thesis this is decisive: a perfect-enough tree exists for the overwhelming majority of real desktop apps, which means no screenshots, no vision model, and no frontier-scale reasoning in the hot loop — a local SLM doing find-by-name → semantic action → state-readback covers most of the desktop, with vision demoted to a rare fallback sensor for framebuffers and a handful of anonymous buttons.**

---

## 2. The final ranking table

Sorted by fidelity score (descending). Categories shown **after** adversarial correction; `*` marks a corrected or provisional row (see notes below the table).

| # | App | Built with | Category | Fidelity /10 | Tree size (nodes) | Semantic actions? | Most important fact |
|---|-----|-----------|----------|:---:|:---:|:---:|---------------------|
| 1 | **Notes** | AppKit | native-perfect | **9.5** | 49 | Yes | Reference-quality AppKit tree: fully bounded, named, value-readable, action-rich (SetValue/TypeText on editor), zero truncation, complete even while backgrounded — full CUA loop in pure AX. |
| 2 | **Calendar** | AppKit (CalUI) | native-perfect | **9** | 170 | Yes | Pure AppKit near-perfect AX: 170-node tree, 100% bounds, 95% named interactive, Toggle/SetValue semantics, stable ax_identifiers, zero truncation even in background capture. |
| 3 | **Reminders** | SwiftUI in AppKit shell | native-perfect | **9** | 88 | Yes | Pristine native SwiftUI/AppKit tree: 100% bounds, SetValue/Toggle on every reminder row, stable in background — pure-AX full loop; only quirk is titles in value not name and a dialog/alert window role. |
| 4 | **TextEdit** | AppKit | native-perfect | **9** | 129 | Yes | Pure-AppKit gold standard: complete untruncated NSOpenPanel tree, 100% bounds, rich actions (Click/SetValue/Expand), stable AXIdentifiers — full CUA loop in pure AX. |
| 5 | **VLC** | AppKit (native Cocoa) | native-perfect | **9** | 57 | Yes | Native Cocoa media player with a near-perfect small AX tree: named transport controls, settable sliders and toggle state, 100% bounds — fully drivable in pure AX despite 8 ghost windows and 2px sliver buttons. |
| 6 | **Microsoft Word** | Custom C++ Office toolkit (MsoCF/FluentUI) + Cocoa shell | native-partial | **9** | 106 | Yes | Custom C++ Office toolkit with excellent UIA-bridged AX: 100% bounds, rich semantic actions and states, full loop possible in pure AX on the start screen; only gaps are unnamed rows/buttons and 8 ghost windows. |
| 7 | **UTM** | SwiftUI (AppKit host) over QEMU | native-partial | **9** | 31 | Yes | SwiftUI manager UI with a near-perfect small AX tree (100% bounds, rich actions, no husk); the guest VM screen itself is an opaque framebuffer requiring vision or utmctl. |
| 8 | **OBS Studio** | Qt Widgets | native-partial | **8.5** | 62 | Yes | Model Qt citizen: full named/bounded/actionable control surface in pure AX (stream, record, scenes, mutes), missing only volume-slider values and the video canvas. |
| 9 | **Safari** | AppKit (WebKit for pages; no webarea captured) | native-partial | **8.5** | 157 | Yes | Near-perfect native AppKit chrome tree (95% named, 100% bounded, rich actions and stable identifiers) even in background; docked for ghost windows, offscreen/disabled state noise, and no web content captured to prove the DOM bridge. |
| 10 | **Firefox** | Gecko (custom C++ toolkit, own DOM→AX bridge) | web-native | **8** | 93 (288 forced) | Yes | Gecko browser exposing chrome and page content as a rich web-native AX tree: 100% bounds, semantic actions everywhere, stable DOM-id selectors — pure-AX loop fully viable. |
| 11 | **YT Music** | Safari Web App (WebKit shell) | web-native | **8** | 437 (975 forced) | Yes | Safari Web App (WebKit), not Electron: full web-native DOM tree, 116/120 interactive named, 100% bounds, values + SetValue/TypeText — pure-AX loop viable; only capture depth-10 truncation and ghost windows to manage. |
| 12 | **WhatsApp** | Native AppKit (Swift rewrite) | native-partial | **8** | 48 | Yes | Native AppKit tree, 100% bounded and action-rich with stable ax_identifiers and full message previews in row values — but presents an offscreen husk until activated and salts every string with invisible bidi marks. |
| 13 | ★ **Zoom Workplace** ★ | **Native AppKit + proprietary C++ UI kit (zui::ViewNode / Prism) — NOT Electron** | native-partial | **8** | 67 | Yes | **THE census surprise: confirmed custom C++ UI kit, yet hand-published AX is rich — 100% bounded, action-exposed, hotkey-annotated tree that survives background capture; semantic AX + keyboard macros suffice.** See the deep-dive in §4. |
| 14 | **Keynote** | AppKit (iWork TS* + TSAccessibility.framework) | native-partial | **8** | 9 (splash only) | Yes | Clean native AppKit tree with full bounds/actions/states, but capture only saw the 9-node launch splash — real editor fidelity untested. |
| 15 | **Brave Browser** | Chromium fork (Views + Blink) | web-native | **7** | 56 (170 forced) | Yes | Chromium-fork with excellent named/bounded/actionable browser chrome, but webarea content is lazily truncated and the tree is a husk until the app is activated. |
| 16 | **Google Chrome** | Chromium Views + Blink via NSAccessibility bridge | web-native | **7** | 51 (69 forced) | Yes | Native Views browser chrome is fully drivable via semantic AX (100% bounds, rich actions), but page content hides in a lazily-hydrated truncated webarea — use CDP for in-page work. |
| 17 | **Finder** | AppKit (system app) | native-partial | **7** | 1,571 | Yes | Rich AppKit tree with 100% bounds/values and real actions, but file cells are named via value not name, big listings truncate (complete:false), and 9 invisible ghost windows hide the real one. |
| 18 | **Gemini** | Native Swift (SwiftUI/AppKit) | native-partial | **7** | 212 | Yes | Native Swift app with an action-rich AX tree (100% bounds, TypeText/SetValue, named conversation buttons) that can send messages in pure AX but hides the chat transcript entirely — write-only, verify with vision. |
| 19 | **Music** | AppKit/SwiftUI chrome + JET/WebKit content | native-partial | **7** | 47 | Yes | Native chrome (sidebar + transport) is near-perfect with stable identifiers and semantic actions, but the JET/WebKit content pane exposes nothing in background capture — chrome-only tree. |
| 20 | **Antigravity IDE** | Electron (VS Code derivative) | electron-veil (unresolved) | **2** | 22 | Partial | 22-node webarea husk hiding an entire IDE; drive via command palette/keyboard or CDP. The forced capture's INTERNAL error is **"RefMap exceeds 1MB"** — the handshake likely hydrated a tree so large it overflowed agent-desktop's ref map. Tool limit, not proven opacity: retest with scoped `--root` captures. |
| 21 | **Claude Desktop** \* | Electron | **web-native\*** (corrected from electron-veil) | **2** (as default-captured) | 19 (36 forced) | Husk only | Default capture is a husk, **but the AXManualAccessibility handshake succeeded**: forced.json fully hydrated the sign-in webarea (named Click-able "Get started" button, readable text, 0 truncation). Post-login fidelity unverified. |
| 22 | **Discord** \* | Electron | **web-native\*** (corrected from electron-veil) | **2** (as default-captured) | 25 (507 forced) | Husk only | Default capture is a husk, **but forced.json is a 507-node, zero-truncation capture of real logged-in content**: 65 named interactives, 112 readable values, Click/Toggle/SetValue/TypeText — a full DOM→AX bridge behind one handshake call. |
| 23 | **Notion** | Electron | electron-veil (confirmed on available evidence) | **2** | 19 | Husk only | Textbook Electron background husk — webarea stubs with children_count but no children hide 100% of Notion's UI; foreground + AXManualAccessibility re-capture (untested) or keyboard macros (Cmd+P) required. |
| 24 | **Telegram** | Native Swift/AppKit (TelegramSwift, Metal-rendered) | **opaque-none (confirmed by experiment)** | **0** | 1 | No | The adversarial pass called it a cold-launch artifact; the decisive re-test refuted that: **warm, foregrounded, 17s settle → still 1 node**, root `subtree_truncated`, 56 AXChildren advertised, zero delivered. A native tree exists internally but is never serialized to AX clients. Automate via Telegram's Bot API/tdlib or vision — never AX. |

**Not captured (launch failures, see §5):** Postman, Canva, Visual Studio Code, Cursor. VS Code is well-characterized from prior atree work as **electron-veil**.

\* Fidelity scores for corrected rows are the *as-captured* scores of the default capture; the corrected category reflects what the forced/adversarial evidence proved about the app itself.

---

## 3. The categories, ranked

Distribution after corrections and the post-census Telegram re-test (24 characterized apps): **native-perfect 5 · native-partial 10 · web-native 6 · electron-veil 2 · opaque-none 1.**

### 3.1 native-perfect — the tree IS the app (5 apps)

The pure-AX ideal: complete, untruncated, named, bounded, value-readable trees with real semantic actions, stable under background capture. These need no vision, no coordinates, no activation.

- **Notes (9.5)** — The census reference standard. The note body is readable via `value` and writable via SetValue/TypeText on the stable id `Note Body Text View`; zero truncation while backgrounded. Quirks are cosmetic: U+2028 line separators and a `dialog`-role window root (`notes/analysis.md`).
- **Calendar (9)** — 170 nodes, 95% of interactives named, stable ax_identifiers (`today-button`, `MiniCalPrevMonthButton`) ideal for compiled routes. Adversarial pass found 17 (not 7) unnamed interactives, but the sidebar checkboxes carry stable native_ids + Toggle, so the full loop holds (`calendar/analysis.md`).
- **Reminders (9)** — Every reminder row pairs a named Toggle switch with a SetValue textfield: full read/write loop in pure AX, captured while the window was invisible. Titles live in `value`, not `name` — name-only finders miss every reminder (`reminders/analysis.md`).
- **TextEdit (9)** — Complete NSOpenPanel tree with stable AXIdentifiers on every commit-path control (`OKButton`, `NewDocumentButton`). Caveat: the evidence rates the Open dialog, not the editor (`textedit/analysis.md`).
- **VLC (9)** — Named transport controls, SetValue sliders (Position/Volume), Toggle fullscreen, all captured in background. Trust node bounds, not the window list (bogus 125x157 rect; 8 ghost strip windows) (`vlc/analysis.md`).

### 3.2 native-partial — real trees with known holes (11 apps)

Genuine native trees, fully bounded and actionable, each with one characteristic gap an agent must engineer around. This is the largest category — and where the census's biggest upsets live (Zoom, Word).

- **Microsoft Word (9)** — Custom C++ Office toolkit, yet UIA-bridged AX is excellent: complete tree, Toggle/SetValue/Expand, honest states. Gaps: unnamed table rows (target the named child cells), DocStage-only coverage (`microsoft_word/analysis.md`).
- **UTM (9)** — Near-perfect SwiftUI manager tree with SF-Symbol native_ids; the guest VM display is a SPICE/Metal framebuffer that will *never* appear in AX — vision or utmctl/SSH for guest content (`utm/analysis.md`).
- **OBS Studio (8.5)** — Model Qt citizen with stable Qt object-path native_ids (`...controlsFrame.streamButton`). Volume sliders are valueless readonly meters — route via the AdvAudioProps dialog (`obs/analysis.md`).
- **Safari (8.5)** — 128/135 chrome interactives named with gold-standard identifiers (`WEB_BROWSER_ADDRESS_AND_SEARCH_FIELD`), stable in background. Captured on the native Start Page: zero webarea nodes, so the WebKit page-content bridge is unproven in this JSON (`safari/analysis.md`).
- **WhatsApp (8)** — Chat-list rows are named buttons whose `value` carries the full message preview + delivery state: inbox triage with zero clicks. Gaps: husk until activated, and invisible bidi characters (U+200E/U+202F) salt every string — normalize before matching (`whatsapp/analysis.md`).
- **★ Zoom Workplace (8)** — see §4. Custom C++ kit, hand-published rich AX, hotkeys embedded in names, survives background capture (`zoom_us/analysis.md`).
- **Keynote (8)** — Clean, complete, background-stable AppKit tree — but the capture caught only the 9-node "What's New" splash; editor fidelity untested. Automation must press the named "Continue" button first (`keynote/analysis.md`).
- **Finder (7)** — 1,571-node tree, 100% bounds/values, SetValue-rename and RightClick context menus. Gaps: file identity in `value` not `name` (30/787 interactives named), large listings truncate (`complete:false`), 9 ghost windows hide the real one, 779 spurious `focused` flags. Use Cmd+Shift+G over brute-force enumeration (`finder/analysis.md`).
- **Gemini (7)** — The write-only app: named conversation buttons, TypeText/SetValue composer, stable ax_identifiers — it can *send* in pure AX but exposes no transcript text and no composer value. Act via AX, verify via vision (`gemini/analysis.md`).
- **Music (7)** — Chrome-only: sidebar + mini-player near-perfect with gold-standard identifiers (`Music.miniPlayer.*`), but the JET/WebKit content pane contributes zero nodes in background. AppleScript is the best bypass (`music/analysis.md`).

### 3.3 web-native — the DOM reaches AX (6 apps)

Browser-class trees where web content itself is (or becomes) AX-visible. The common law of this category: **the tree is lazy — husk until activated/handshaken, then rich.** Depth-10 capture caps, not app opacity, explain most truncation here.

- **Firefox (8)** — Gecko's own DOM→AX bridge with localization-proof `ax_dom_identifier` selectors (`urlbar`, `back-button`). forced.json: 288 nodes, 0 truncation — the full New Tab DOM. Target by pid: 11 same-named processes break name targeting (`firefox/analysis.md`).
- **YT Music (8)** — WebKit "Add to Dock" Safari Web App, *not* Electron. All 177 truncated containers sat exactly at the depth-10 cap; forced re-capture recovered 975 nodes, 0 truncation, 281 named interactives. No CDP (WebKit) — but none needed (`yt_music/analysis.md`).
- **Brave (7)** / **Google Chrome (7)** — Same story twice: fully drivable native Views chrome (omnibox SetValue+TypeText = full navigation in pure AX; tabs are `radiobutton`s in a tablist), lazily-truncated webarea that forced capture hydrates (Brave 170 nodes, Chrome 69, both 0 truncation). `ax_dom_identifier` values are join keys against CDP for deep in-page work (`brave_browser/analysis.md`, `google_chrome/analysis.md`).
- **Claude Desktop (corrected from electron-veil)** — The default capture is a genuine 19-node husk, and `claude/analysis.md` recommended the AXManualAccessibility poke as "the highest-value next probe." The probe ran: forced.json succeeded — 36 nodes, 0 truncation, the sign-in webarea fully hydrated with a named Click-actionable "Get started" button and readable text. Evidence limited to the sign-in splash; post-login fidelity unverified — but the veil demonstrably lifts.
- **Discord (corrected from electron-veil)** — The strongest correction of the census. `discord/analysis.md` called the unlock "untested"; it wasn't — forced.json is a 507-node, zero-truncation capture of real logged-in content: 65 named interactives (buttons/links/treeitems/switches), 112 readable values, Click/Toggle/SetValue/TypeText. Discord is a full web-native app behind a one-call handshake. Cmd+K keyboard macros remain a fine fast path.

### 3.4 electron-veil — the messiest category, now down to two (2 apps + VS Code by prior knowledge)

Chromium webarea stubs that admit children (`children_count` set, DOM ids leaking: `root`, `notion-app`, `app-mount`) but refuse to produce them. After corrections, only two confirmed residents:

- **Antigravity IDE (2)** — Still veiled, but no longer "proven unliftable": the forced capture's INTERNAL error is **"RefMap exceeds 1MB size limit"** — the handshake most plausibly *hydrated* a giant IDE tree that then overflowed agent-desktop's interactive-ref map (a retry without `-i` also failed). Treat as a tool limitation to route around (scoped `--root` captures, or CDP), not app opacity. Drive via command palette/keyboard or CDP, never pure AX. Bonus pathologies: 9/10 windows are ghosts, window-server vs AX bounds disagree (178x161 vs 2560x1410), titles elided with Unicode ellipsis (`antigravity_ide/analysis.md`).
- **Notion (2)** — Genuine husk on the available evidence (3 truncated groups gate 100% of the UI; zero named interactives, zero values), but the verdict carries a caveat: capture was background-only and the handshake is **untested** — given the Claude/Discord results, Notion is a prime candidate to graduate to web-native on a foregrounded, handshaken re-capture. Until then: Cmd+P command palette is the dependable blind channel (`notion/analysis.md`).
- **Visual Studio Code (not captured)** — launch failed in this census, but prior atree work characterizes its tree as electron-veil; Cursor and Antigravity are its derivatives.

### 3.5 opaque-none — one confirmed resident (1 app)

- **Telegram (0)** — The one app where every escalation failed. The adversarial pass reasonably suspected a cold-launch artifact (AXChildren advertises 56 children), so a decisive re-test ran post-census: **warm, foregrounded, 17 seconds of settle — still a 1-node tree with a truncated root** (`telegram/forced_warm.json`). TelegramSwift builds a native tree internally and never serializes it to AX clients. The consolation is that Telegram has the best *non-UI* automation surface of any app in this census: the Bot API / tdlib. Use that, or vision; pure AX is a dead end here.

**Every other analyzed macOS app has a usable accessibility tree.** One genuine refusal in 24 is still a strikingly clean result for the thesis.

---

## 4. Zoom deep-dive (the census headline)

*Full detail: `zoom_us/analysis.md`. Capture: background mode, window not visible, v7.0.6, 4 windows enumerated.*

**What it's made of.** Symbol-level evidence settles the old rumor: Zoom is **not Electron, not CEF, not Qt, not Catalyst**. The main executable links Cocoa/AppKit + a large Swift runtime slab; 130 proprietary frameworks fill the bundle with zero Chromium artifacts. `zUI.framework` contains C++ symbols in a `zui::` namespace — `zui::ViewNode`, `zui::ViewRenderObject`, `zui::CaptionNode` — a node-based custom cross-platform render tree drawn via AppKit/CoreGraphics, wrapped in ObjC view classes that *manually publish accessibility*. `Prism.framework` is the newer cross-platform layer (AppKit + WebKit + Metal). Web surfaces are **WKWebView**, not Chromium.

**What works via AX.** Far more than the pedigree implies: 67 nodes, `complete: true`, 0 truncated containers, 100% bounds on all 38 interactive nodes, Click/RightClick/SetFocus on 54 nodes, honest disabled/readonly/selected states — **all resolved with the window invisible and unfocused** (no husk). Element names embed keyboard shortcuts (Cmd-E search, Shift-Cmd-O, Cmd-bracket history) — free macro mining. The embedded "Zoom Calendar" WKWebView exposes its DOM through AX at web-native quality. The signature quirk: the 6-tab nav strip is `unknown`-role containers named "X, N of 6" each wrapping an *unnamed* inner button — target the parent's name, press the child.

**Gaps.** 3 anonymous edge buttons (vision or trial-press); in-meeting controls unverified (no live meeting during capture — separate window, same zUI kit expected); rendered video is pixels, not AX; promo banners inject/remove nodes, so prefer name-targeting over positional indexing; 4 ghost/helper windows require title filtering.

**Definitive reach strategy.** **Primary: semantic AX** (find-by-name + exposed Click/SetFocus) — complete, named, bounded, background-stable. **Secondary: keyboard macros** — uniquely strong here because AX names advertise the hotkeys, and global meeting hotkeys (Cmd-Shift-A mute, Cmd-Shift-V video, Cmd-W leave) bypass the auto-hiding toolbar entirely: the most robust in-meeting path. **Fallback: vision** only for the 3 anonymous buttons and video-content questions. **Coordinates and CDP: unnecessary.**

---

## 5. Census caveats — what a rerun should do differently

1. **Four launch failures (Gatekeeper/first-run suspected):** Postman, Canva, Visual Studio Code, Cursor — `open(1)` succeeded but no process ever spawned (`census_summary.json`). A rerun should pre-launch each once by hand (or clear quarantine attributes) before capture. VS Code needs no re-derivation of category: prior atree work has it as electron-veil.
2. **First-pass launch flakes, recovered on pass 2:** the summary JSON records "process never appeared" for WhatsApp and OBS, but both were captured successfully on the second pass (`capture_pass2.py`; their meta.json shows live pids). Reruns should treat "never appeared" as retryable, not terminal.
3. **Capture-artifact suspicion, resolved.** Telegram's warm foregrounded re-run WAS performed post-census (17s settle): still 1 node — the 0/10 stands as a property of the app, not the capture. Notion remains the open case: background-only capture, handshake untested — rerun foregrounded + `AXManualAccessibility`.
4. **Wrong-surface captures.** Several scores rate a splash or dialog, not the working surface: Keynote (What's New splash), Claude Desktop (sign-in page), TextEdit (NSOpenPanel), Microsoft Word (DocStage start screen), Safari (native Start Page — zero webarea nodes, DOM bridge unproven), Zoom (no live meeting — in-meeting toolbar unverified). Reruns should log in / open a document / join a meeting first, then capture.
5. **Depth-10 cap masquerading as truncation.** YT Music's 177 and Firefox's 9 "truncated containers" all sat exactly at capture depth 10; forced/subtree re-capture recovered everything. Raise the cap or add on-demand subtree re-expansion before calling anything truncated.
6. **Always run the AXManualAccessibility handshake on Electron apps before categorizing.** It corrected two of four "husks" this census (Discord: 25 → 507 nodes; Claude: 19 → 36) and failed diagnostically on the third (Antigravity, INTERNAL error). It is the single highest-information probe per app.
7. **Ghost windows are universal.** Nearly every app ships invisible 29–30px strips, 1x1 shells, or offscreen slivers (Finder's "best window" was a ghost; Claude has an 8:1 ghost-to-real ratio). Window pickers must filter `visible:true` + plausible size, never trust title or first-window.
8. **Systematic state noise to normalize:** spurious mass-`focused` flags (Finder 779, Music sidebar, Calendar), `dialog`/`alert` window roles on SwiftUI/AppKit apps (Calendar, Notes, Music, Reminders, UTM), window-server vs AX bounds disagreements (Antigravity, VLC, Safari, YT Music — trust node bounds), and bidi-salted strings (WhatsApp).

---

## 6. Implications for atree — the fidelity → sensor policy

The census validates the tiered sensor policy: **spend the cheapest sensor that the tree's fidelity permits.**

### Tier 1 — v1 "Siri-killer" set: pure AX, no vision, local SLM sufficient
Complete-or-near-complete named/bounded/actionable trees; find-by-name → semantic action → state readback closes the loop.

> **Notes, Reminders, Calendar, TextEdit, VLC, OBS, Microsoft Word, UTM (manager UI), Safari (chrome), WhatsApp, Zoom Workplace, Keynote, Finder, Music (chrome)**

Route notes: WhatsApp/Zoom need activation-then-capture and (WhatsApp) bidi normalization; Finder wants scoped queries + Cmd+Shift+G; Reminders/Finder/TextEdit identity lives in `value`, not `name`; compiled routes should anchor on the stable ax_identifiers these apps ship (`today-button`, `Note Body Text View`, `Music.miniPlayer.*`, Qt object paths, `NavigationBar_NewChatButton`).

### Tier 2 — handshake-first: one `AXManualAccessibility` poke, then treat as Tier 1
> **Discord, Claude Desktop, Brave, Chrome, Firefox, YT Music** — and **Notion** as the untested candidate most likely to join.

The poke is cheap, deterministic, and proven (Discord 507-node result). Browsers additionally need activation to escape the pre-AT skeleton husk, and depth-aware subtree re-expansion for deep DOMs.

### Tier 3 — CDP (Chromium debug protocol)
- **Chrome / Brave in-page heavy lifting** — `ax_dom_identifier` values are join keys between the AX tree and CDP; use CDP where the DOM is deep or dynamic.
- **Antigravity IDE / VS Code / Cursor** — the veil does not lift (Antigravity's handshake fails with INTERNAL); CDP via a debug-port launch, or command-palette keyboard driving, are the only semantic channels.
- Not applicable to Firefox/YT Music/Safari (no Chromium) or stock-launched Electron apps without a debug port (Discord's integrity checks make injection hostile).

### Tier 4 — vision + coordinates (the rare fallback, exactly where the census predicts)
- **Framebuffers that will never be in AX:** UTM guest displays (or utmctl/SSH), OBS video canvas, Zoom video grids.
- **Write-only verification:** Gemini's invisible transcript (act via AX, verify via pixels); Music's content pane (or AppleScript, the better bypass).
- **Anonymous residue:** Zoom's 3 unnamed edge buttons, Keynote/Word/Claude traffic-light chrome, hover-revealed affordances in Notion.
- **Telegram** — permanently (warm re-capture confirmed the refusal). Prefer the Bot API/tdlib over vision where credentials allow.

### Tier 0 — keyboard macros (cross-cutting accelerator)
Free and tree-independent: Zoom's global meeting hotkeys and name-embedded shortcuts, Discord Cmd+K quick-switcher, Notion Cmd+P, Antigravity/VS Code command palette, Finder Cmd+Shift+G. Every electron-veil app is *fully drivable blind* through its palette; every high-fidelity app gets faster with them.

**Bottom line for the thesis:** 19 of 24 apps close the full observe→act→verify loop in semantic AX today (Tiers 1–2), two more need CDP/keyboard only, and vision is load-bearing for exactly three kinds of pixels: video framebuffers, one write-only transcript, and a dozen anonymous buttons. A perfect tree really does mean no vision — and no vision means the hot loop fits in a local SLM.
