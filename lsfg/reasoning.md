# lsfg: reasoning (the checker)

**Date:** 2026-09-30
**Pairs with:** `implementation.md`. Every `→ Dn` there points to an entry here.

## How to use this file

- **Before you change a decision** in `implementation.md`, find its `D` number below. Read *Why* and *Tripwire*. If your new evidence doesn't meet the tripwire, don't change the decision. If it does, change it, and add a line to the change log (§8).
- **Before you build a module,** run the pre-build checklist (§5).
- **Before you merge anything,** run the review checklist (§6).
- **If something is slow or broken,** check §3 first. Most of what can go wrong here has already gone wrong once, in arc-cua, in atree, or in the codex run.

Entry format: **Decision** · **Why** (evidence, with where it came from) · **Rejected** (other options and why not) · **Tripwire** (what would make us change it) · **Guard** (the test or metric that watches it).

---

## 1. Ground truth: what we measured

### 1.1 Measured today (2026-09-30, this machine, arc-cua venv: Python 3.13.5, PyObjC 12.2.2)

All read-only. The scripts are in `scripts/probes/` (p1–p5, see its README). Re-run them to refresh these numbers. Where two runs gave different numbers (the screen changed between them), both are shown.

| what | result | why it matters |
|---|---|---|
| Permissions for the VS Code host | `AXIsProcessTrusted() = True`, `CGPreflightScreenCaptureAccess() = True` | AX and OCR work from this host today |
| **AX identity across two walks** (p1) | Safari first: `repr` equal **1/8**, `CFHash` **8/8**, `CFEqual` **8/8**. Then all 5 running apps across 3 stacks (Finder, TextEdit, Safari native; YT Music WKWebView; Antigravity Electron): `CFHash` and `CFEqual` **393/393**, `repr` only 1 per app (the root object passed in twice), CFHash distinct within each walk | `repr` holds a memory address; ids built from it change every read (→ D3) |
| **`AXWindows` is not the full window list** | YT Music and Antigravity (windows on another Space, 0 on-screen CG windows): `AXWindows = []`, app `AXChildren` = menu bar only, **but `AXFocusedWindow` and `AXMainWindow` return a real `AXStandardWindow`**. Safari full screen: its window has subrole `AXDialog`. TextEdit running with no window: `AXFocusedWindow` → NoValue (-25212) | the window picker must union all four sources and must not filter to `AXStandardWindow` (→ D23) |
| **arc-cua `settle_probe()` twice on an idle UI** | signatures equal: **False**; ids reused: **0/6**; two full `observe()` revisions equal: **False** (105 elements) | arc-cua's settle loop can never see two equal frames, so it always waits its full timeout (1.5 s click, 2.5 s typing). Its "no change for 3 actions → BLOCKED" never fires (→ D3, D30) |
| Menu bar read (3 app menus, closed) | Safari 0.6 ms (79 items), TextEdit 1.8 ms (58), Finder 0.9 ms (74), YT Music 1.6 ms (44), Antigravity 0.9 ms (59). First call cold: 23–66 ms | the menu is a near-free command index (→ D24) |
| Walk depth 10, batch-only (1 call per node) (p2) | Safari 106–109 nodes / 22–43 ms · Finder (desktop) 16 / 2–5 ms · **YT Music 437 nodes / 98–274 ms with 179–250 leaves-with-children exactly at the cap** · Antigravity 26 nodes with 6–8 at the cap | LAW-STR-6 (silent depth cap) reproduced live on 2 apps (→ D9) |
| Hit-test `AXUIElementCopyElementAtPosition` (p2) | 0.18–0.31 ms median across 4 apps | the pre-click occlusion check is essentially free (→ D25) |
| `CGWindowListCopyWindowInfo` (p3) | 0.5–0.7 ms | fine to call per step |
| Safari's on-screen layer-0 windows (p3) | a **33 px-tall strip listed before the real window** in both runs (2560×33 before 2560×1440; later 1280×33 before 1280×803) | ghost filtering is needed on the CG list too. The codex's `h ≤ 30` misses a 33 px strip, so lsfg uses `h ≤ 40`. Any short strip with no matching AX window is a ghost whatever its width (→ D23) |
| Window capture, nominal resolution (p3) | 2560×1440: 10.5 ms median (max 26.6) · 1280×803: 24.6 ms | in-memory capture is cheap (→ D21) |
| Vision OCR on that capture (p3) | 2560×1440: fast 14 ms (5 texts), accurate 117 ms (8) · 1280×803: fast 15 ms (11), accurate 147 ms (27) · top-20% crop fast 6.9–7.8 ms | `fast` is the default; crops are cheaper still (→ D21) |
| **JEV** (`jev-latest` → model `jev-1.13.0`), synthetic payloads | cold first call **613 ms**; warm **342–410 ms** (10, 100, 200 options; 1 question); **406–505 ms** (4 questions × 100 options). Input ~42 tokens per option (692 tokens at 10 options, 8,492 at 200) | about 0.35–0.5 s per call, almost flat in options; the network and server floor dominates (→ D5, D26, D28) |

### 1.1b Measured while building (2026-09-30, lsfg code, live)

| what | result | changes |
|---|---|---|
| **E2** background AX menu press | TextEdit File>New pressed via AX in **2 ms** while Antigravity stayed frontmost; the new window's close button pressed via AX closed it | confirms D24: menu and AX actions work in the background |
| **E3** activation from lsfg's process | with Antigravity IDE frontmost, **none** of AXFrontmost, NSRunningApplication.activate, NSWorkspace open (activates=YES), `open -b`, the Dock item's AXPress, or AppleScript `activate` brought Finder/Safari forward (tested inside and outside the Claude Code sandbox) | activation is best effort (D33 updated); lsfg remembers the failure for 120 s so it stops paying ~2 s per try; typing falls back to AXValue; pointer/keys fail with a clear FocusLost |
| **E10** page URL | Safari's webarea `AXURL` read `https://www.youtube.com/` | the `url` check works on Safari |
| **M1 acceptance** `lsfg "open youtube on safari"` | SUCCESS, 0 model calls: **2.3 s** with Safari cold (launch + load); with Safari warm, lsfg's own work was **56 ms** (URL hand-off) + **85 ms** (URL check) | built-in intents no longer require "frontmost" as the goal (E3) |
| WebKit page content cost | `AXChildren` ≈ **1.1 ms per call** on web nodes vs ~0.1 ms for other attributes; a 626-node YouTube page walks in 1.1–1.3 s | resolve checks the last snapshot first and validates the node with 1 IPC before any re-walk |
| locked screen | `loginwindow` frontmost; every app's `AXFocusedWindow`/`AXWindows` return the application element | new `ScreenLocked` error (B31) |
| JEV through lsfg's own client | picked "Priya Sharma" over "Priya's sister" among 6 synthetic rows in 471 ms ($0.000025); the same question from the per-task cache in 0.2 ms; a non-existent chat → no pick | confirms D5/D29 wiring |
| census law replay with lsfg's ports | ghosts 130/161; Finder 0/751 typeable textfields while Calendar 7/7 and VLC 1/1 are; CLASSIFY 24/24; Safari anchors 40/40 resolve | the ports match the codex |
| **E6** the anyOf schema | the API refused it: 400 "The compiled grammar is too large, which would cause performance issues" (1.8 s wasted). The flat schema was accepted | flat is the default (D15 updated). anyOf stays as an option |
| **M2 first planner task** `open my gmail and search the mail from space by matthew` | SUCCESS: 1 Opus call at effort low, **7.6 s** (cold: first use of the schema, and it wrote the cache), **3,528 in** (3,381 of them a 1 h cache write: system prompt + schema) / **246 out**, **$0.0326**. Plan: one `open_url` in Brave to Gmail's `#search/from:matthew space` + a `url` check, passed in 537 ms. The window title then read "Search results … Gmail" | cold cost is mostly the cache write; the next call in the hour reads those 3.4k tokens at 1/40 the price |
| same task again | route r1 replayed: **0.3 s, 0 model calls, $0**; the route became trusted (2/2) | confirms D18 (routes) end to end |
| planner context before the fix | the task word "space" pulled in a running app called Space, and the frontmost Brave's current page (card + digest, ~1.8k tokens) went to Opus for a task that opens its own site | new rules in D40: plain-word app names need app context; the screen goes in only when the task doesn't name its target or says "this"/"here" |

### 1.2 Measured earlier (arc-cua `LATENCY_IMPROVEMENT.md`, 2026-09-21, same machine)

| what | result |
|---|---|
| PyObjC bridge overhead | 0.96 µs per call |
| one AX attribute read | Safari 15 µs · Finder 1,228 µs |
| 11 attributes batched vs 11 separate | Finder 1,220 µs vs 13,391 µs · Safari 45 vs 183 · System Settings 305 vs 828 |
| arc-cua original walk | 14 IPC calls per node; Finder 278 nodes in 4.8 s; batched prototype 976 ms (4.9×) |
| System Settings batched | **slower** (469 ms vs 175 ms). Batching is per-app, not a universal win |
| modal scan on every observe | 89 ms on a 28-element app (3× the AX walk), found nothing |
| OCR fast | 10–110 ms per window; accurate 5–8× slower |

### 1.3 From the codex (captures 2026-08-30/31, agent-desktop 0.8.1)

Headline numbers the plan leans on:
- 80.7% of windows are ghosts (130/161).
- (role, name) is unique for 68.1% of named interactives; with bounds, 98.0%.
- AppKit textfield-as-label: Finder 765 per capture, 0 with SetFocus.
- Native max depth 9.
- Electron interactives: median depth 21, max 26.
- Notion default 19 nodes → forced 1,004 (exact prefix).
- Telegram opaque (1 node, 4 captures over 20 min).
- A missing value key means empty (2,455 vs 6).
- JEV-free readiness ladder: sorts 24/24 apps.

**Caveats.** No law was adversarially verified. Some counts sum two captures: "Finder 1516" in `laws.md` is really **765 per capture**. `music/forced.json` is YT Music. `laws.md` says "macOS 15", but these captures were taken on this machine (Darwin 25 = macOS 26). Treat that header as a typo and record the OS version from now on.

### 1.4 From vendor docs (checked 2026-09-30)

| fact | source |
|---|---|
| JEV API: `POST https://api.typesafe.ai/v1/systemone`, Bearer key, `model`, `state` (string/object/array), `questions` map. Types: `choice` (criteria ≤ **255** options), `score` (2–10 levels), `noul`. Answers carry `probabilities` and `confidence` (not noul). Errors: 401, 422, 429, 529 | docs.typesafe.ai/api |
| JEV known weak spots: literal reading, arithmetic, counting, date comparison, large irrelevant state. Questions are answered independently whether bundled or not | MarkTechPost coding guide (2026-09-23) |
| TypeSafe's own browser agent: "a DONE decision still requires independent outcome verification"; "model output never becomes a selector, coordinate, shell command" | explainx write-up of jev-ultrafast |
| Opus 5.5: `claude-opus-5-5`; $4 in / $20 out per MTok; cache read $0.20; 1 h cache write $8; prompt-cache minimum **512 tokens** | platform pricing + prompt-caching docs |
| Opus 5.5: adaptive thinking always on; `thinking: disabled` → 400; `effort` default **medium**; levels low…max | platform effort docs |
| Structured outputs GA: `output_config.format` (json_schema). No recursion; `additionalProperties: false` required; ≤ 24 optional params total; ≤ 16 union-typed params; grammar compiled on first use, cached 24 h | platform structured-outputs docs |
| Fast mode: `speed: "fast"` + beta `fast-mode-2026-02-01`, up to 2.5× output tokens per second, $8/$40, research preview, breaks the prompt cache when switched | platform fast-mode docs |

### 1.5 From our own history (things users actually hit)

- atree v1 in Claude Code: "5 min and 12k tokens to open a Notion page", plus screenshots nobody needed.
- agy + atree MCP typed character by character, even though clipboard paste was in `learnings.md`.
- Opening apps went through Spotlight, which the user never wanted.
- Antigravity (Gemini Flash) did a simple terminal task in < 20 s; Claude + atree took 1 min 30 s.
- atree v2 analysis (`theoratically.md`): a local observe is ~100 ms, one frontier call is 3–8 s, and v1's 6-turn WhatsApp route took 30–50 s, of which about 600 ms was real work.

---

## 2. Decisions

### D1 · lsfg is a new project, not a fork of arc-cua and not an atree plugin

- **Decision:** a fresh package that copies specific, audited pieces of arc-cua (MIT) and atree, and ports agent-desktop's normalization rules.
- **Why:**
  - arc-cua has foundation bugs in exactly the parts that decide speed and correctness: repr-based ids (§1.1), a deadline that isn't propagated, CLICK from AXShowMenu, text entry offered on labels, and trusting JEV's SUBTASK_COMPLETE by default (`verify=None → True`). It's also someone else's repo (Isle), with the user's uncommitted local changes.
  - atree's architecture puts the frontier model in the loop, one tool call per action. That's the "5 min / 12k tokens" problem (§1.5).
  - lsfg needs the planner, memory, and codex rules that neither has.
- **Rejected:**
  - Patching arc-cua in place: the fixes touch its models, runtime, backend, and policy, so it's a rewrite wearing its name, and it drifts from upstream.
  - Extending atree: its unit of work is a Claude Code tool call.
- **Tripwire:** arc-cua upstream fixes identity + action space and adds a planner/verify hook → consider contributing lsfg's perception back and depending on it.
- **Guard:** the `NOTICE` file lists every copied function; the §3 table lists what must never be copied.

### D2 · Python + PyObjC, in-process. No agent-desktop CLI, no FFI, no Swift daemon for v1

- **Decision:** walk AX directly from Python with batched calls.
- **Why:**
  - The bridge is 0.08% of a Finder AX call. The cost is IPC count, not language (§1.2).
  - A CLI spawn costs about 50 ms per call (atree v2: Rust binary ~20 ms + Node shim ~30 ms), and v1 paid it on every action.
  - In-process we measured a Safari walk of 106 nodes in 22 ms.
  - Python also gives us the Anthropic SDK and httpx HTTP/2 in the same process.
- **Rejected:**
  - agent-desktop FFI: "days", an FFI memory contract, and `panic = abort` hazards. Its speed comes from batching, which we copy.
  - A Swift daemon: no speed gain (same IPC count), and more languages to maintain.
  - The agent-desktop CLI: spawn cost on every call.
- **Tripwire:**
  - profiling shows > 20% of a step's time in Python itself (not IPC, not network), or
  - we need `ad_wait`-class native predicates we can't match with polling.
- **Guard:** `timings_ms` + `ax_calls` in every observe trace; bench p50 per step type.

### D3 · Element identity = (pid, CFHash(ref)); session aliases on top

- **Decision:** key every element by `CFHash`, confirm with `CFEqual` on collisions, and give it a short alias (`e12`) that stays the same across walks.
- **Why:**
  - Measured: `CFHash`/`CFEqual` stable on 393/393 nodes across 5 apps and 3 stacks (native, WKWebView web app, Electron), while `repr` matched only the root object (§1.1).
  - arc-cua's repr-based ids made idle-UI signatures differ every time (p5: 0/16 ids reused), so settling always hit its timeout and no-change detection never fired.
  - Stable ids also enable targeted re-reads by ref (1 IPC for a check instead of a walk), JEV decision caching, and alias-based plans.
- **Rejected:**
  - `repr(ref)`: measured unstable.
  - Structural path strings (atree `axdiff`): stable, but they break when a sibling is inserted, and they cost string work per node. We still use paths for route selectors (§8.1), not for session identity.
  - `hash(ref)`: Python's hash of a PyObjC proxy is not guaranteed to follow `CFHash`.
- **Tripwire:** E1 shows CFHash changing for the same element across walks in any framework (still to test: Gecko, Qt, Catalyst, and neighbors changing between walks) → fall back to (role, identifier, label, bounds, parent key) matching for that framework.
- **Guard:** unit test "same key keeps alias"; the live test E1 on 5 apps; an `identity_collision` counter in traces (must stay ~0).

### D4 · The model is not the loop

- **Decision:** Opus writes one short plan. The local executor runs all steps and checks them in code. Opus is called again only on failure (≤ 2 replans).
- **Why:**
  - Frontier calls cost 3–8 s each; local steps cost 20–300 ms (§1.5).
  - v1's 6-turn route spent 30–50 s to do about 600 ms of work.
  - atree v2's own analysis reached the same conclusion ("stop making the model the loop").
- **Rejected:**
  - The model calling tools per step (atree v1, Claude Code, MCP): granularity is the problem, not the transport.
  - JEV-only with no planner (arc-cua as shipped): it can't decompose tasks, can't write literal inputs or checks, and has no memory.
- **Tripwire:** new-task success < 70% because plans are too coarse → allow the planner a "checkpoint" op that returns control after N steps with a fresh digest (still not per-step).
- **Guard:** trace counts of Opus calls per task; bench "planner-bound" share.

### D5 · Three tiers: route (no model) → Opus (plan) → JEV (choices)

- **Decision:** JEV is called only for `choose`, ambiguous targets, and `explore`. Never for checks, never for text.
- **Why:**
  - JEV measured 0.35–0.5 s per call (§1.1). That's fast, but not free: 10 JEV steps is 4–5 s. So deterministic resolution comes first, and JEV only where a real choice exists (a list of results, chat rows).
  - JEV can't write text, which matches the arc-cua invariant that literal inputs come from the planner.
  - It's cheap: ~$0.0003 per call.
- **Rejected:**
  - JEV for every step (arc-cua): slower than deterministic resolution and exposed to its weak spots.
  - Haiku/Sonnet per step: 1–3 s per call and free-text failure modes.
  - A local SLM: no model we have is faster than 0.35 s end to end with calibrated probabilities, and we'd have to host it.
- **Tripwire:**
  - JEV p50 > 800 ms for a week, or its access changes → swap `decide/jev.py` for a local chooser behind the same interface.
  - JEV wrong-pick rate > 10% at τ = 0.6 (E7) → raise τ, or add the planner's `want` literal matching before JEV.
- **Guard:** JEV latency and confidence histograms; wrong picks detected by failed post-checks.

### D6 · JEV (and any model) never decides success

- **Decision:** `DONE`/`goal_met` only triggers evaluation of typed checks in code.
- **Why:**
  - JEV is weak at literal reading, counting, and dates (§1.4).
  - TypeSafe's own agent verifies DONE separately.
  - arc-cua's `_verify_completion` returns True when no verify callback is set, so "complete" was whatever JEV said.
- **Rejected:** a JEV `noul` "is it done?" as the verdict (weak spot); a VLM check (latency, not in v1).
- **Tripwire:** none planned. This is a safety invariant.
- **Guard:** an engine test that a plan whose checks fail can't end in SUCCESS, even if JEV says DONE with 1.0.

### D7 · Checks are typed, closed, and never substring scans over a tree

- **Decision:** a closed list of 10 check kinds with exact semantics (§11.1 there), OR/AND groups, and validation that rejects empty patterns.
- **Why:**
  - ATree_tool's `folder_name in str(tree)` reported success when the open had failed: the path was still sitting in the picker's text field (atree `postconditions.py` docstring).
  - atree's `title_matches` once matched everything on an empty pattern.
  - A closed list is something the planner can learn and code can verify.
- **Rejected:** free-form "verification sentences" judged by JEV (arc-cua), since models can't be trusted to judge; arbitrary Python predicates from the planner, since that's code execution.
- **Tripwire:** ≥ 3 bench tasks that can't be expressed with the 10 kinds → add a kind (with tests), never a free-form escape hatch.
- **Guard:** validator tests; every check kind has a unit test on fixtures.

### D8 · Never sleep; always wait for a specific condition

- **Decision:** `wait_checks`, `resolve_wait`, and `wait_quiet` replace every fixed delay. There are two tiny, named exceptions (a 30 ms double-click gap; a 120 ms paste wait when the field can't be read).
- **Why:**
  - arc-cua's settle loop waited 0.18–0.65 s minimum and, with unstable ids, always the full 1.5–2.5 s (§1.1).
  - ATree_tool tasks were full of fixed sleeps (atree's supersession table).
  - Checks are cheap to poll (1–3 IPC per poll on fast apps), so waiting on the real condition is both faster and more reliable.
- **Rejected:**
  - "Wait until the UI stops changing" as the default: slow, and it never stabilizes with a blinking caret on pixel hashes (LATENCY Phase 4).
  - Fixed floors per action type: they're only right on average.
- **Tripwire:** a class of app where checks pass too early (half-rendered state) causes wrong next steps → add a per-app `min_settle_ms` in its profile (measured), not a global floor.
- **Guard:** trace `wait` records (polls, ms); a lint rule that bans `time.sleep` outside `act/pointer.py` and `act/clipboard.py`.

### D9 · Walk budgets by stack; the deadline is checked at every node; continue at the frontier

- **Decision:**
  - native depth 12 / web depth 45 / nodes 1,500–3,000 / deadlines 700–1,500 ms
  - an iterative walk that checks the deadline per node
  - frontier continuation instead of re-walks
  - AXManualAccessibility on Electron once per launch
- **Why:**
  - Native interactives never go below depth 9 (LAW-STR-3).
  - Web content reaches depth 30 (Notion), and a depth-10 cap silently cuts it (LAW-STR-6, LAW-LIFE-1). Reproduced live: YT Music had 250 leaves at the cap.
  - arc-cua's recursive `_walk` passes the deadline only to the root call. The children get `deadline=None`, so the 2 s budget never actually stopped a walk.
  - LAW-LIFE-1 says the deeper tree is a strict superset, so continuing from the frontier refs is exact and cheaper than re-walking.
  - AXManualAccessibility is Electron's documented switch for assistive clients. The codex couldn't rule out that agent-desktop had already enabled it before its captures (LAW-LIFE-1 exception), so we set it ourselves rather than rely on history.
- **Rejected:**
  - One depth for everything (arc-cua 18): cuts Electron, and wastes time on native.
  - Skeleton + drill loops (atree): many round trips.
  - AXEnhancedUserInterface: side effects on window animations in some apps.
- **Tripwire:** a native app with interactives below depth 12 (law_event) → per-app depth in its profile. E5 shows AXManualAccessibility changes nothing and costs time → drop it.
- **Guard:** the trace fields `frontier`, `truncated`, and per-stack walk ms; the live YT Music test.

### D10 · Port agent-desktop's normalization exactly; make capability probes lazy

- **Decision:** the role map (Appendix D), the name order, and the capability rules are copied verbatim from `roles.rs`, `evidence_fields.rs`, and `action_list.rs`. The settable probes run only when a rule needs them.
- **Why:**
  - All 71 laws were measured in agent-desktop's vocabulary (Click, SetFocus, TypeText, textfield, …). If our words mean something different, the laws don't transfer.
  - `IsAttributeSettable` has no batch form (1 IPC each), and probing everything cost about 330 ms per Finder walk (LATENCY Phase 3).
  - Most nodes never need a settable answer. Only text-entry, expand, and select candidates do.
- **Rejected:**
  - arc-cua's mapping: CLICK from AXPress or AXShowMenu; TYPE_TEXT/SET_VALUE on any settable field.
  - Probing everything up front: slow on Finder-class apps.
- **Tripwire:** agent-desktop changes its rules → re-port and re-run the fixture tests.
- **Guard:** unit tests against the census fixtures, where `available_actions` is ground truth from agent-desktop itself.

### D11 · Clean the action space before JEV sees it

- **Decision:** the candidate filters in §12.2 there: `interactive()`, `typeable()`, no RightClick-only, no zero-area, no disabled, readonly out, secure out, a scope limit, lexical ranking, and a cap of 200 + NONE.
- **Why:**
  - LAW-ACT-6: AXShowMenu sits on 74–100% of static text in web stacks, so arc-cua offered almost every text node as a click target.
  - LAW-ACT-8: Finder 765 file-name labels were offered as typing targets.
  - JEV's weak spot is large irrelevant state.
  - The API caps choice options at 255.
  - `NONE` lets JEV say "nothing fits" instead of being forced into a wrong pick.
- **Rejected:** sending everything (arc-cua, up to 240 per kind, duplicated in `state`); no NONE option.
- **Tripwire:** E7 shows the correct element being filtered out in > 2% of cases → loosen the specific rule that removed it (the trace says which).
- **Guard:** trace `jev.n_candidates`; a unit test that Finder yields 0 typeable textfields; a golden test that a known target is present after filtering.

### D12 · Actuation mode per stack, learned per app

- **Decision:**
  - native: AXPress (in the background)
  - Electron/CEF: pointer first
  - web in browsers: AXPress, then check, then pointer
  - Qt: AXPress only
  - opaque: pointer on OCR boxes
  - The profile records which mode actually passed its checks, per (app, role).
- **Why:**
  - atree `catalyst.md`: AXPress is reliable on native and works without stealing focus.
  - atree `electron.md`: in Notion, AXPress returns ok and changes nothing (React routing).
  - atree `qt-opaque.md`: OBS has no bounds, so only AXPress is possible.
  - LAW-LIFE-4: native trees are fully usable in the background.
  - Our checks detect a "silent success", which makes per-app learning possible and safe.
- **Rejected:** pointer everywhere (steals focus, needs activation, and fails on hidden or other-Space windows); AXPress everywhere (swallowed in React).
- **Tripwire:** an Electron app where AXPress passes checks ≥ 5 times in a row → the profile flips it to AXPress automatically (that's the learning working, not a doc change).
- **Guard:** `press_mode` changes are logged as law_events; the bench recovery rung 1 rate.

### D13 · Text entry: paste for event-driven fields, AXValue for native form fields, always verify the value

- **Decision:** the §9.4 decision table there; clipboard paste with full restore; never character by character by default.
- **Why:**
  - The user watched agy type one character at a time.
  - atree rule 5 (from ATree_tool learnings): paste is atomic and registers with Electron/React.
  - React-controlled inputs ignore AXValue sets (atree: "never trust semantic set-value in Electron").
  - Native form fields accept AXValue in one IPC, and it's exact.
  - LAW-TXT-1/7: verify by value key presence and equality, never the name.
- **Rejected:** per-character CGEvent typing (slow; drops characters in some apps); AXValue everywhere (doesn't trigger search-as-you-type or React state).
- **Tripwire:** E4 shows native search fields do trigger on AXValue → use AXValue for them too (faster, no clipboard). An app blocks paste → profile flag `type_mode = unicode_chunks`.
- **Guard:** a `value` post-check on every type step (validator-enforced); the clipboard restore test (E8).

### D14 · Open apps and URLs through LaunchServices; never Spotlight, never osascript

- **Decision:** `NSWorkspace.openApplicationAtURL…` / `openURLs…withApplicationAtURL…` with `activates=True`; our own app index built from `Info.plist` files.
- **Why:**
  - The user explicitly never wants Spotlight.
  - atree rule 4.
  - osascript to control apps triggers Automation (AppleEvents) permission prompts per host app, and spawns a process.
  - LaunchServices also sends "reopen" to running apps, which creates a window when there is none (what atree used osascript `reopen` for).
- **Rejected:** `open -a` as the primary path (a process spawn; kept only as a fallback); osascript (permissions, spawn); `mdfind` to find apps (Spotlight's index; can be stale or disabled).
- **Tripwire:** an app that LaunchServices can't reopen into a window → a per-app profile step (e.g., the menu item File>New Window).
- **Guard:** the `open_app` post-check (frontmost + window); `doctor` app index count.

### D15 · Structured outputs with a compact, flat-ish schema

- **Decision:**
  - `output_config.format` with the op table schema
  - all fields required
  - checks at the top level, pointing at steps
  - compact selector strings with digest aliases (`@e12`)
  - one repair round on validation errors
- **Why:**
  - Grammar-constrained output removes "invalid JSON" failures.
  - The API limits (≤ 24 optional params, ≤ 16 unions) rule out optional fields and nested per-step check unions. Top-level checks keep it to 2 unions.
  - Output tokens are the planner's latency. Aliases (`@e12`, ~2 tokens) and selector strings are far shorter than nested objects, in line with atree v2's target of about 150 tokens for 10 steps.
- **Rejected:**
  - Free-text DSL: shortest, but not grammar-constrained.
  - Tool use with a forced tool: same token cost as the schema, older mechanism.
  - Deeply nested step objects: exceed the union limits and cost more tokens.
- **Tripwire:** E6 shows the API rejects `anyOf` of `const`-tagged objects → switch to the flat schema (already specified). Measured output > 400 tokens for ≤ 5-step plans → shorten field names or move to a tuple form.
- **Result of E6 (2026-09-30):** the tripwire fired. The anyOf schema (14 step shapes + 10 check shapes) was refused with "compiled grammar is too large", so **flat is the default**. The flat plan for a 1-step, 1-check task was 246 output tokens. If longer plans get slow, shorten field names first.
- **Guard:** trace `plan.tokens.out`, `repair` rate, invalid-plan rate.

### D16 · Opus 5.5 at effort `low` for plans, `medium` for replans; fast mode optional

- **Decision:** as stated. Never send a `thinking` parameter.
- **Why:**
  - Opus 5.5 always thinks adaptively, and disabling it is an error (§1.4). Effort is the only dial.
  - Low effort means fewer thinking tokens, and output tokens are the latency.
  - Replans are rarer and harder, so they get medium.
  - Fast mode is 2.5× output speed at 2× price, but it's research-preview access and a cache split.
- **Rejected:**
  - Default medium for everything: slower for no gain on 1–5-step plans (to be confirmed in E6).
  - Sonnet 5.5 or Haiku 4.5 as the planner: the user chose Opus 5.5. It stays configurable (`planner.model`), and a `fallback_model` exists but is off.
- **Tripwire:** E6 shows effort low produces invalid or weak plans (> 10% repair rate, or bench success drops ≥ 10 points vs medium) → use medium. Fast-mode access granted and planner-bound latency > 40% of task time → enable fast.
- **Guard:** per-effort bench runs in M2; trace `plan.ms`, `ttft_ms`, `tokens.out`.

### D17 · Prompt caching: a static system prompt (1 h) + app cards (5 min), sorted

- **Decision:** two cache breakpoints, the system prompt first, cards second, sorted by bundle id. Nothing per-request (time, task) before the breakpoints.
- **Why:**
  - Opus 5.5 caches ≥ 512 tokens; our system prompt is about 900.
  - Cache reads cost 5% of base ($0.20/MTok) and cut prefill time.
  - Placing a timestamp before a breakpoint destroys the cache (docs' common mistake).
  - Sorting cards makes equal app sets byte-identical.
- **Rejected:** no caching (pays ~$0.02 more per plan and more TTFT); putting the digest in the cached part (it changes every time).
- **Tripwire:** `cache_read_input_tokens == 0` on > 20% of plans within the TTL → find what varies in the prefix.
- **Guard:** trace `tokens.cached`; a unit test that the rendered system block is byte-stable across two tasks.

### D18 · Routes: saved plans with slots, compiled without a model when possible, always re-verified

- **Decision:**
  - route = template + regex + stored plan with selectors (never refs or aliases) + checks
  - deterministic slot compile
  - Opus compile only when a literal isn't a clean task span
  - candidate → trusted → stale → disabled; patch on self-healed runs
- **Why:**
  - The pitch's "database of every successful run": replay beats reasoning.
  - LAW-ID-8: refs die with the snapshot, and this is the most common way compiled routes rot.
  - Re-verifying every replayed step makes a stale route fail safe (it falls back) instead of silently doing the wrong thing.
  - A deterministic compile saves an Opus call per new task.
  - Refusing to guess when a literal differs from the task span ("Get Lucky Daft Punk" vs "get lucky") stops routes from replaying the old literal.
- **Rejected:**
  - Fuzzy (embedding/FTS) route matching (atree `find_route` used FTS as a fallback): wrong-route replays.
  - Storing aliases or paths only: aliases die with the process; paths break when siblings change.
- **Tripwire:** route hit rate < 20% after 2 weeks of real use → add paraphrase aliases from planner `route` picks (already planned), then consider JEV route routing.
- **Guard:** route stats (runs, passes, consecutive fails); unit test "template compile + match".

### D19 · Irreversible steps: pre-checks + confirmation by default + heuristic backup

- **Decision:** §16.1 there.
- **Why:**
  - atree safety invariant: recipient verification before typing into a message field.
  - Models mislabel risk sometimes, so a label heuristic (Send, Delete, Pay…) backs the planner up.
  - Default confirmation is cheap (1 keypress) compared with the cost of a wrong send.
  - JEV below 0.85 and `explore` near irreversible steps are exactly the "wandering near a Send button" failure.
- **Rejected:** trusting the planner's risk flag alone; no confirmation ever (the Siri dream, but one wrong message is worse than one extra keypress).
- **Tripwire:** after 100 irreversible confirmations with 0 declines on verified pre-checks → offer `auto_when_explicit = true` as the default.
- **Guard:** an engine test that irreversible steps can't run without pre-checks; a count of confirmations and declines in traces.

### D20 · Privacy: send the least, locally keep the rest, deny sensitive apps

- **Decision:** the §16.3 table there; a denylist carried over from atree; no screenshots leave the machine; traces local with an optional label hashing; no telemetry.
- **Why:**
  - JEV and Opus both receive UI text, which includes names, previews, and file names (the codex saw this in WhatsApp, Finder, Calendar).
  - The vision.md risk section flagged this.
  - atree already had the "selectors, not content" rule and a denylist.
- **Rejected:** masking everything by default (it hurts JEV's matching, and it's the user's own data going to vendors they chose); sending screenshots (privacy + latency).
- **Tripwire:** the user asks for stricter handling, or a new app category (health, finance) is used → add it to the denylist or turn on `mask_content`.
- **Guard:** `redact.py` unit tests; a check that denylisted apps produce 0 JEV calls and 0 digest lines.

### D21 · OCR: in-memory CGImage + Vision `fast` + crops + one-entry pixel-hash cache

- **Decision:** as in §7 there.
- **Why:**
  - Measured capture 10.5 ms + fast OCR 14 ms on 2560×1440; crops 6.9 ms (§1.1).
  - No disk writes: faster and more private.
  - `accurate` is 5–8× slower with no gain for choosing (LATENCY).
  - One cache entry per window avoids stale coordinates (LATENCY Phase 6 trap).
- **Rejected:** writing PNGs + a Swift OCR helper (atree `ocr.swift`: a process spawn + disk); ScreenCaptureKit first (more code for no speed gain today).
- **Tripwire:** `CGWindowListCreateImage` returns None or is removed in a macOS update → ship the SCK path (already the planned fallback).
- **Guard:** `doctor` capture test; trace OCR ms.

### D22 · No vision model in v1

- **Decision:** no screenshots to any model; OCR only.
- **Why:**
  - AX gives usable trees for 22 of 24 census apps (only Telegram is opaque, and Gemini's transcript is write-only), and OCR covers both.
  - Cloud VLM calls are seconds and ship pixels (privacy).
  - Local VLMs weren't measured on this machine for this job.
- **Rejected:** a cropped-VLM verification rung (atree v2 §6 rung 4): a good idea, but it's v2 and needs measurement.
- **Tripwire:** ≥ 3 bench tasks fail only because neither AX nor OCR can see the answer → prototype the cropped local-VLM rung.
- **Guard:** the recovery rung histogram (unverifiable failures).

### D23 · AX windows are the truth; CG windows only for capture ids, with ghost filters

- **Decision:**
  - `pick_window` works on the **union** of `AXWindows`, the app's `AXChildren` windows, `AXFocusedWindow`, and `AXMainWindow` (de-duplicated with `CFEqual`)
  - no subrole filter beyond "window or dialog"
  - CG windows matched by exact bounds
  - strips filtered with `h ≤ 40 & (w ≥ 1000 or no AX match)`, plus helper sizes and thumbnails
- **Why:**
  - 80.7% of window-server entries were ghosts (LAW-WIN-1).
  - Bounds are exactly right or wildly wrong (LAW-WIN-5).
  - An empty list isn't "no window" (LAW-WIN-10).
  - Live today, Safari listed a 33 px strip before its real window in both runs. The codex's `h ≤ 30` rule would have captured the strip.
  - Live today, windows on another Space were **missing from `AXWindows` and `AXChildren`** (YT Music, Antigravity) but still returned by `AXFocusedWindow`/`AXMainWindow`. A picker that trusts `AXWindows` alone would report "no window".
  - Safari full screen reports subrole `AXDialog`.
- **Rejected:** CG-first picking (arc-cua OCR's `front_window` with a size filter of 80 px caught this strip, but it's fragile); agent-desktop `list-windows` (subprocess).
- **Tripwire:** a real window ≤ 40 px tall and ≥ 1000 px wide shows up (e.g., a toolbar-only app) → add an AX-match override: a strip that matches an AX window is kept.
- **Guard:** windows fixtures (130/161, 0 FP); live Safari test.

### D24 · The menu bar is a first-class command channel

- **Decision:**
  - index menus per app version
  - put shortcuts in app cards
  - a `menu` op that presses items by path
  - `hotkey` only for shortcuts from the index or a small standard set
- **Why:**
  - Measured 0.6–1.8 ms to read 3 menus, with items readable while closed (§1.1).
  - Menu presses don't depend on the keyboard layout or on coordinates.
  - The planner stops guessing shortcuts (atree `electron.md` said keyboard macros win, but the model had to remember them).
- **Rejected:** hotkeys from model memory (wrong across app versions and layouts); clicking through menus with the pointer.
- **Tripwire:** E2 shows background menu presses fail for most apps → activate before `menu` (a small cost), keeping the op.
- **Guard:** the menu press live test; trace `menu` step pass rate.

### D25 · Hit-test before every pointer click

- **Decision:** the element at the click point must be the target or within 3 parents of it.
- **Why:** it costs 0.18 ms (§1.1). It catches popovers, banners, and moved windows, the classic "clicked the wrong thing" failure. arc-cua and atree clicked blind at bounds centers.
- **Rejected:** trusting bounds (LAW-LIFE-6: bounds belong to one snapshot); screenshot diffing (slow).
- **Tripwire:** E9 shows hit-test disagrees with reality > 5% for a framework (e.g., Chromium returns the webarea for everything) → accept "webarea ancestor + bounds contain the point" for that framework.
- **Guard:** E9; pointer-step failure analysis.

### D26 · A warm daemon and a single cache table

- **Decision:** an optional long-lived daemon keeps frameworks, DB, HTTP/2 connections, cards, and aliases warm. Every cache is listed with its key and invalidation (§14.7 there).
- **Why:**
  - JEV cold 613 ms vs warm ~350 ms (§1.1). TLS setup is paid once.
  - PyObjC imports cost hundreds of ms per cold start.
  - atree v2 reached the same conclusion ("one long-lived process").
  - Listing every cache in one table stops silent stale-data bugs, the kind that burned us with snapshot-scoped refs.
- **Rejected:** a daemon-only design (harder to debug; the CLI must work without it); caches spread through modules without a registry.
- **Tripwire:** the in-process CLI p50 within 10% of the daemon → make the daemon optional-only (it already is).
- **Guard:** bench runs with and without the daemon; an invalidation unit test per cache.

### D27 · The codex laws live in code, are tested on the census fixtures, and are watched in use

- **Decision:** each law maps to a function and a test (Appendix A there). Contradictions at runtime become `law_events`.
- **Why:**
  - The laws are strong but unverified (no adversarial pass, single-surface bias).
  - Real use is the verification pass we never ran: each time a law's prediction fails, we record it.
  - The census JSON is agent-desktop ground truth, so the tests are cheap and offline.
- **Rejected:** treating laws as prose in prompts only (untestable); ignoring them (repeats every mistake the census found).
- **Tripwire:** a law with ≥ 5 law_events → revise it in the codex and in code together.
- **Guard:** the weekly law_events review (M4).

### D28 · JEV candidate cap 200 + NONE; relevance ranking first

- **Decision:** as stated.
- **Why:** the API limit is 255 options. Latency is flat in option count (§1.1), but tokens and irrelevant state grow with it, and irrelevant state is JEV's weak spot. Ranking by lexical overlap with the step keeps the true target in the list while cutting noise.
- **Rejected:** arc-cua's 240 per operation kind, repeated across questions.
- **Tripwire:** E7 shows the true target is ranked out of the top 60 in > 2% of cases → widen to 120 before touching the rules.
- **Guard:** golden choose cases.

### D29 · Confidence gating and a per-task decision cache

- **Decision:**
  - accept when confidence ≥ 0.60 (safe) or ≥ 0.85 (before irreversible) and the top-2 margin is ≥ 0.15
  - a deterministic exact-label shortcut before any call
  - a per-task decision cache
- **Why:**
  - JEV is trained for calibrated probabilities; the SDK guide's production example uses stake-based thresholds (0.50/0.85/0.90).
  - The margin catches the "two Priyas" case.
  - The exact-label shortcut removes calls when the literal is known.
  - The cache is per task, because the screen changes between tasks.
- **Rejected:** always taking argmax (arc-cua); a persistent cross-task decision cache (stale screens).
- **Tripwire:** E7 calibration shows accepted picks < 95% right → raise τ; > 99% right with many rejects → lower τ.
- **Guard:** the confidence histogram vs outcomes in traces.

### D30 · No-change and loop detection on stable signatures

- **Decision:** the signature hashes (alias, role, label, value, states) of a shallow walk. 3 equal signatures after actions → STUCK. The same target 3 times → STUCK.
- **Why:** this only works because aliases are stable (D3). arc-cua's version never fired (§1.1). atree v2 noted that "parallelising doesn't fix loops; loops need a loop detector".
- **Rejected:** revision hashes over every node including OCR geometry (LATENCY R5: never stabilizes).
- **Tripwire:** animations (spinners) keep signatures changing forever → exclude `busy` subtrees from the signature.
- **Guard:** an explore unit test with a static FakeAX (must stop at 3).

### D31 · Huge lists: visible rows only, no drilling

- **Decision:** fan-out caps + `AXVisibleRows`/`AXVisibleChildren`; TRUST_PREFIX; reach the rest by scrolling or in-app search.
- **Why:**
  - Finder listed 765 items per capture.
  - Drilling a truncation boundary worked 0/7 times, up to 45 s each (LAW-LIFE-7).
  - Enumeration loss is a stable prefix, and retrying doesn't help.
- **Rejected:** full enumeration (seconds on slow AX servers); agent-desktop `--root` drills.
- **Tripwire:** tasks that need an item far down a list fail > 10% → add a "search first" hint to the app card for that app.
- **Guard:** walker fixture tests with Finder; trace `truncated.fanout`.

### D32 · Opaque apps go straight to OCR

- **Decision:** readiness R2 marks an app `OPAQUE` on the first capture and stores that in its profile.
- **Why:** Telegram gave the same 1-node tree over 4 captures and 20 minutes, in background and foreground (LAW-LIFE-8). Waiting or activating never helped.
- **Rejected:** retrying AX with waits (wasted seconds every time).
- **Tripwire:** a Telegram update exposes a tree (n > 12) → the profile resets on version change automatically.
- **Guard:** the ready fixture (Telegram → OPAQUE); the profile reset test.

### D33 · Physical input requires frontmost + focus guards; AX actions never activate

- **Decision:** as in §9.6/§9.8 there.
- **Why:**
  - atree `catalyst.md`: keystrokes leak into the terminal running the agent when the app isn't frontmost; activating before semantic clicks steals focus for nothing.
  - macOS 14+ cooperative activation may block focus requests from background processes, so we verify focus instead of assuming it.
- **Rejected:** `CGEventPostToPid` for background keystrokes (unreliable across apps; worth testing later); no guard (keystroke leakage).
- **Result of E3 (2026-09-30):** from lsfg's process inside the IDE, every activation method was refused (§1.1b). So activation is best effort: `focus.activate` tries AXFrontmost and NSRunningApplication (fast), then AppleScript once; after a full failure it skips the slow path for 120 s. Anything that needs physical input fails with `FocusLost` and says why; everything else uses background AX actions, which work.
- **Tripwire:** activation works from a plain Terminal (worth testing: `scripts/probes/p6_activation.py`) → recommend running lsfg from Terminal for pointer/keyboard-heavy tasks.
- **Guard:** a unit test that `keys.post()` refuses without the guard; the live leakage test (type with the wrong app frontmost → refused).

### D34 · The clipboard protocol restores everything, only after the paste lands

- **Decision:** save all pasteboard items and types → write text with transient markers → guard → Cmd+V → value check → restore if `changeCount` is unchanged.
- **Why:**
  - atree restored text only (it skipped images and files).
  - Restoring before the app reads the pasteboard can paste the old content.
  - A changeCount guard avoids overwriting something you copied during the run.
  - Transient markers keep clipboard managers from recording our temporary text.
- **Rejected:** no restore (clobbers your clipboard); a fixed 500 ms wait (atree), which is slow.
- **Tripwire:** E8 shows some type fails to restore (e.g., promised file data) → skip saving those types and warn.
- **Guard:** E8; a unit test with a fake pasteboard.

### D35 · A synchronous engine; threads only for overlapping I/O; one task at a time

- **Decision:** as stated.
- **Why:** one desktop means one task. AX calls go to one app at a time anyway. The only useful overlap is the planner call and read-only prefetch. asyncio would add a second concurrency model next to PyObjC run loops for no gain.
- **Rejected:** full asyncio (complex); parallel tasks (they'd fight over focus and the clipboard).
- **Tripwire:** we need streaming plan execution (D38) → a small producer/consumer queue between the planner thread and the executor, still no asyncio.
- **Guard:** the global lock test.

### D36 · Tests: fixtures first, then live, then golden; the bench verifies independently

- **Decision:** as in §19 there.
- **Why:**
  - The census gives us ~30 MB of real trees for free, offline tests.
  - Live tests are slow and change your desktop, so they're opt-in.
  - Golden traces catch engine regressions without tokens.
  - A bench that trusts the plan's own checks can't catch weak checks, so the bench carries its own.
- **Rejected:** live-only testing (slow, flaky, disruptive); mocks with invented trees (they'd miss the real quirks).
- **Tripwire:** fixture tests pass but live tests fail on the same rule → the fixture converter is wrong (fix it before anything else).
- **Guard:** CI runs unit + golden; live runs before each milestone exit.

### D37 · Build order: the deterministic core first, with no models

- **Decision:** M1 ships "open youtube on safari" and "search lofi on youtube" with zero model calls before any planner code exists.
- **Why:**
  - Everything the models do depends on perception, resolution, action, and checks being right.
  - Bugs there look like model failures and waste model debugging time. This happened with arc-cua's settle loop.
  - It also gives the user something that works in about two days.
- **Rejected:** building the planner first (impressive demos that fail for local reasons).
- **Tripwire:** none. This is ordering, not a claim.
- **Guard:** the milestone exit criteria.

### D38 · Streaming plan execution is deferred until measured

- **Decision:** v1 waits for the full plan. M4 adds "start step 0 while later steps stream" only if planner time dominates.
- **Why:** it saves roughly the time to generate the steps after the first (maybe 1–3 s), but adds partial-parse and cancel logic. Adaptive thinking comes before the JSON anyway, so the first step can't start before thinking ends.
- **Rejected:** building it in M2 (complexity before evidence).
- **Tripwire:** traces show planner generation after the first step > 30% of new-task time.
- **Guard:** trace `plan.ms` vs `ttft_ms` vs first-step completion.

### D39 · Route matching is deterministic (regex templates)

- **Decision:** full regex matches only; ties or no match → the planner (which can pick a route by id for paraphrases).
- **Why:**
  - Wrong-route replay is worse than a 4 s planner call.
  - Regex matching takes microseconds and is explainable.
  - The planner already sees the routes list, so paraphrases still reach routes, and each paraphrase becomes an alias (learning).
- **Rejected:** FTS or embedding similarity for replays (atree used FTS as a fallback: fast, but it can replay the wrong task); JEV route choice without slot extraction (JEV can't extract text).
- **Tripwire:** route hit rate stays low while the planner keeps picking routes by id for paraphrases → auto-add those paraphrases as aliases (planned) and measure again.
- **Guard:** route stats; match unit tests.

### D40 · The planner sees a digest with aliases, never raw trees

- **Decision:** ≤ 150 lines, about 2.3k tokens, wrapper chains collapsed, aliases for referencing.
- **Why:**
  - A raw Notion tree was 1.9 MB (~473k tokens) in ATree_tool.
  - The median full tree is ~2,900 tokens and Finder's is 78k (atree v2 census).
  - Aliases cut the planner's output tokens, which is the latency.
  - Collapsing wrapper chains is lossless (LAW-STR-4).
- **Rejected:** full trees (cost + latency); no screen info at all (the planner guesses selectors blindly).
- **Tripwire:** plans fail because the needed element wasn't in the digest > 5% → raise the cap for that app (the profile) or add "nearby text" lines.
- **Guard:** trace resolve failures tagged `not_in_digest`.

### D41 · Opus 5.5 is the planner (your choice), configurable

- **Decision:** `planner.model = "claude-opus-5-5"`.
- **Why:** you asked for Opus 5.5. It's the strongest model for the one call that must decompose the task, write literal text, and write checks. At one call per new task, the cost is ~$0.02.
- **Rejected:** a smaller planner by default (weaker plans, more replans; replans cost more time than the model speed saves).
- **Tripwire:** E6 shows Opus p50 > 10 s for simple plans, and Sonnet 5.5 at the same success rate is < 50% of that → offer "Sonnet for ≤ 3-step tasks" as a config profile.
- **Guard:** planner metrics per model in the bench.

### D42 · Built-in intents and a sites map, before routes and the planner

- **Decision:** 5 regex intents + a small `sites.json` (search URL templates).
- **Why:** "open X", "open site in browser", and "search Q on site" are the Siri-class tasks. They need no model and no UI: one LaunchServices call plus checks. That's the < 2 s experience you asked for ("replace Siri").
- **Rejected:** sending them through the planner (3–8 s for something a regex can do); a large site database (maintenance, wrong guesses).
- **Tripwire:** an intent misfires (e.g., "open mail" meaning the site) twice → tighten the regex or the app-over-site rule.
- **Guard:** intent unit tests with near-miss phrasings.

### D43 · Selectors are strings with a small grammar

- **Decision:** the §8.1 grammar there.
- **Why:** compact for the planner (tokens), readable in logs, storable in routes, and one parser shared by planner output and routes. It covers the whole LAW-ID-12 chain: identifier, DOM id, role + label, value, nth, scope.
- **Rejected:** nested JSON selector objects (more tokens, more schema unions); XPath-like paths (brittle, LAW-ID-11).
- **Tripwire:** the planner makes selector syntax errors in > 5% of plans → add grammar examples to the prompt, or move selectors into the schema as objects.
- **Guard:** the repair-reason histogram.

### D44 · Budgets are hard caps

- **Decision:** the §2 table there.
- **Why:** ATree_tool and atree v1 both had runs that "kept doing" things for minutes. Caps turn a runaway into a clear failure report, and they bound cost (worst case about 3 Opus calls ≈ $0.06 + 30 JEV ≈ $0.02 per task).
- **Rejected:** no caps; soft warnings.
- **Tripwire:** ≥ 5% of successful bench tasks come within 20% of a cap → raise that one cap.
- **Guard:** trace `task_end` budget usage.

### D45 · Irreversible steps are never retried or replanned automatically

- **Decision:** when an irreversible step's action runs and its post-check fails (or the action raises), the step fails. No second actuation mode, no JEV, no explore, no replan.
- **Why:** a "failed" Send may have sent. The post-check can fail for reasons unrelated to the action (slow UI, a check that reads the wrong element). Retrying turns one uncertain send into two sends. Found while building the recovery ladder; the first version of the plan allowed rungs 1 and 5 here.
- **Rejected:** retrying with the other mode (the double-send risk); replanning (the planner would improvise near a Send button).
- **Tripwire:** traces show many irreversible failures that were actually fine (the action landed, the check was wrong) → fix the checks, not the rule.
- **Guard:** `tests/unit/test_engine.py::test_irreversible_is_never_retried`.

---

## 3. Bugs and mistakes found in the code we build on (never repeat these)

| # | where | what | proof | lsfg fix |
|---|---|---|---|---|
| B1 | arc-cua `macos_ax._stable_id` | ids = sha1(`repr(ref)`), and repr holds a memory address | 1/8 equal across walks (§1.1) | CFHash keys (D3) |
| B2 | arc-cua `macos_hybrid.settle_probe` + `runtime._observe_after_action` | the signature includes those ids, so it never stabilizes and waits the full timeout on every action | 0/6 ids reused, signatures differ on idle UI (§1.1) | stable aliases + check-driven waits (D8, D30) |
| B3 | arc-cua `runtime` no-change guard | `state_changed` is always True, so BLOCKED never fires | same | D30 |
| B4 | arc-cua `macos_ax._walk` | the deadline isn't passed to recursive calls, so only the root checks it; `truncated` is computed after the fact but the walk never stops | code read (`self._walk(..., depth=depth + 1)` has no deadline) | iterative walk, deadline checked per node (D9) |
| B5 | arc-cua `_element_from_ref` | CLICK if AXPress **or AXShowMenu** | LAW-ACT-6 (74–100% of web static text has AXShowMenu) | Click only from AXPress/AXOpen/AXConfirm (D10) |
| B6 | arc-cua `_element_from_ref` | TYPE_TEXT + SET_VALUE on every settable textfield | LAW-ACT-8 (Finder 765 labels) | `typeable()` (D11) |
| B7 | arc-cua `TypeSafeJevPolicy` | the element list sits in `state` and again in each target question's `criteria` | code read | state small; candidates only in criteria (D11) |
| B8 | arc-cua `DesktopExecutor._verify_completion` | returns True when no verify callback is set, so JEV's word is final | code read | D6 |
| B9 | arc-cua `macos_ocr._looks_like_text_input` | hard-coded strings tuned to Spotify ("whatdoyouwanttoplay") | code read | removed; typing targets come from AX or the planner |
| B10 | arc-cua `macos_hybrid` (before local changes) | a deep modal scan on every observe | LATENCY R2 (89 ms for nothing) | sheet check on the picked window only |
| B11 | arc-cua `macos_ax.observe` | always reads the frontmost app, so it can't read a background app | code read | target app by bundle id/pid (LAW-LIFE-4) |
| B12 | arc-cua `_scroll` | the scroll wheel goes wherever the cursor is, not over the target | code read | warp over the scroll area and restore (§9.3) |
| B13 | atree v1 | the frontier model is the loop (one tool call per action) | 5 min / 12k tokens for a Notion page; 30–50 s WhatsApp | D4 |
| B14 | atree v1 run | screenshots to find elements | user report | AX first; OCR only for opaque apps; no VLM (D22) |
| B15 | agy + atree MCP | typed character by character | user report | paste by default (D13) |
| B16 | agy/atree runs | apps opened via Spotlight | user report | LaunchServices (D14) |
| B17 | atree `core/snapshot.run` | a subprocess (and a Node shim) per action | ~50 ms each (atree v2) | in-process (D2) |
| B18 | ATree_tool | success = substring over the serialized tree | atree `postconditions.py` docstring | typed checks (D7) |
| B19 | atree `title_matches` (fixed later) | an empty pattern matched everything | atree history | validator rejects empty patterns (D7) |
| B20 | ATree_tool tasks | fixed sleeps everywhere | atree supersession table | D8 |
| B21 | census, first pass | trusted `complete=true` and a depth-10 cap, and called Electron a "husk that needs a handshake" | LAW-STR-6, LAW-LIFE-1 (Notion 19 → 1,004, exact prefix) | depth by stack + frontier continuation (D9) |
| B22 | codex `laws.md` | the "Finder 1516 labels" figure counts two captures | the per-capture count is 765 | always quote per-capture counts |
| B23 | census | `music/forced.json` is actually YT Music | LAW-STR-12 | the fixture converter asserts `data.app` |
| B24 | agent-desktop `--app` with multi-process apps | AMBIGUOUS_TARGET (Firefox matched 11 processes) | LAW-LIFE-10 | target by pid and bundle id |
| B25 | atree `ax type` | restored text only (images/files lost); a fixed 500 ms wait | code read | D34 |
| B26 | codex ghost rule `h ≤ 30` | misses the 2560×33 strip seen live | §1.1 | `h ≤ 40` + AX match (D23) |
| B27 | the "handshake" story (census README, first explanation to the user) | a wrong mental model, repeated in docs | LAW-LIFE-1 | fixed in the codex README and vision.md; don't reintroduce it |
| B29 | our own first route compiler | accepted a typed text that was only partly in the task, so replaying "play blinding lights" would have typed "blinding lights Daft Punk" | unit test `test_compile_refuses_unmatched_literal` failed on first run | typed text and URL queries must be clean task spans (§14.5) |
| B30 | our own first selector parser | `groupdom#root` parsed as a role named `groupdom`, so 0/18 Notion anchors resolved; ids with spaces (Calendar `previous day`) could not be written at all | the census anchor check | split a trailing `dom`; quoted ids (§8.1) |
| B32 | assuming activation works (the first plan's §9.8) | macOS 26 cooperative activation refused all six methods from a background process | E3 probes, live | best-effort activation; background AX first; FocusLost with a clear message |
| B31 | assuming "no window" means the app has none | on a locked screen every app returns its application element for `AXFocusedWindow` and `AXWindows` | live, 2026-09-30 (loginwindow frontmost) | `ScreenLocked` check before observing/acting |
| B28 | any window picker that reads only `AXWindows` | windows on another Space are missing from `AXWindows` and the app's `AXChildren`, but `AXFocusedWindow`/`AXMainWindow` still return them | §1.1 (YT Music, Antigravity) | union of all four sources (D23) |

---

## 4. Assumptions we have NOT verified yet (each has an experiment in implementation.md §21)

| assumption | experiment | if false |
|---|---|---|
| CFHash is stable across walks for **all** stacks and survives UI changes of neighbors | E1 (done for native, WKWebView, Electron on an idle UI: 393/393; still to do: Gecko, Qt, Catalyst, and with the UI changing between walks) | per-framework fallback identity (D3 tripwire) |
| AXPress on a background app's menu items and buttons works | E2 | activate before `menu`/press for that app (D24) |
| AXFrontmost can take focus on macOS 26 | E3 | LaunchServices first (D33) |
| AXValue on native search fields doesn't trigger search | E4 | use AXValue there too (D13) |
| Setting AXManualAccessibility helps cold Electron apps and has no side effects | E5 | drop it (D9) |
| ~~The Opus schema with anyOf+const is accepted~~ **refused** (grammar too large, §1.1b); flat plans are ≤ 250 output tokens at effort low (246 for 1 step) | E6 | done: flat is the default (D15) |
| JEV at τ = 0.6 picks right ≥ 95% on real tables | E7 | raise τ, more deterministic matching (D29) |
| The clipboard restore keeps rich content | E8 | skip those types (D34) |
| The hit-test agrees for native/web/Electron | E9 | relaxed rule per framework (D25) |
| AXURL exists on webareas in Safari/Chrome/Brave/Electron | E10 | address-field fallback only |
| AXObserver notifications are reliable enough to drive waits | E11 | keep polling (v2 only anyway) |
| US-layout key positions are fine for this user | E12 | build a layout table via `UCKeyTranslate` |
| JEV latency stays ~0.35–0.5 s at other times of day | repeat the §1.1 probe for a week (trace data) | D5 tripwire |
| The laws hold on screens other than the one captured per app (single-surface bias) | law_events in real use | D27 |

---

## 5. Pre-build checklist (run before writing each module)

- [ ] Which laws does this module implement? Name them in the module docstring. Is there a fixture test for each?
- [ ] Does anything here store a ref or an alias? (It must not, except in the session alias table.)
- [ ] Every AX call goes through `ax/raw.py` (counted, with a timeout, errors returned)?
- [ ] Any `time.sleep`? (Only allowed in `act/pointer.py` for the double-click gap, and in `act/clipboard.py` for the unverifiable paste.)
- [ ] Any per-node extra IPC? Is it lazy and needed? Can it be moved into the one batch?
- [ ] Any model call? Is it in the tier table? Is there a deterministic shortcut first? Is it counted in the budgets?
- [ ] What leaves the machine from this module? Is it in the §16.3 table?
- [ ] What is cached here? Is it in the §14.7 table with an invalidation rule?
- [ ] What's the failure class for each error path (closed list §15.4)?
- [ ] Is there a trace record for what this module decides?

## 6. Review checklist (run on every change)

- [ ] No `repr(ref)` anywhere as identity.
- [ ] No deadline that isn't checked inside loops.
- [ ] Click comes only from AXPress/AXOpen/AXConfirm (or container select).
- [ ] No typing into a textfield that fails `typeable()`.
- [ ] No success without typed checks passing in code.
- [ ] No substring checks over serialized trees; no empty patterns.
- [ ] No Spotlight, no osascript for app control, no char-by-char typing by default.
- [ ] Physical input only behind the frontmost + focus guard; AX actions never activate.
- [ ] Pointer clicks only behind the hit-test gate, with bounds from this snapshot.
- [ ] Irreversible steps: pre-checks, no `explore`, JEV ≥ 0.85, confirmation unless configured.
- [ ] Denylisted apps: no JEV, no digest content, no routes.
- [ ] Budgets enforced on every loop that can repeat (recovery, explore, polling).
- [ ] Traces updated; bench still passes; the `law_events` for this change look sane.
- [ ] If a decision changed: a change-log line (§8) with the evidence.

## 7. Things we deliberately don't do (so nobody "adds them back")

| not doing | why | revisit when |
|---|---|---|
| screenshots to models | privacy + seconds of latency; AX + OCR cover the census | D22 tripwire |
| agent-desktop CLI calls in the loop | ~50 ms spawn per call | never for the inner loop |
| full DFS at max depth everywhere | seconds on slow AX servers; the tokens are useless | never; frontier continuation instead |
| drilling truncation boundaries | 0/7 success, up to 45 s | never (LAW-LIFE-7) |
| waiting for Electron to "hydrate" | it was the depth cap | never (LAW-LIFE-1) |
| trusting `complete=true` | silent depth cap | never (LAW-STR-6) |
| first-match on ambiguous selectors | wrong-target clicks | never (LAW-ID-7) |
| storing refs, aliases, or snapshot ids in routes | they die with the snapshot or process | never (LAW-ID-8) |
| per-step frontier model calls | the whole reason for lsfg | never (D4) |
| AppleScript/shell ops in plans | code execution from model output | only as vetted, fixed templates, if ever |
| a persistent JEV decision cache | screens change | never |
| fuzzy route replay | wrong-task replays | D39 tripwire |

## 8. Change log for decisions

| date | decision | change | evidence |
|---|---|---|---|
| 2026-09-30 | all | initial version | §1 measurements, codex, vendor docs |
| 2026-09-30 | D45 (new) | irreversible steps never retried or replanned | found while building the ladder (engine test guards it) |
| 2026-09-30 | D18 | typed text must be a clean task span; `choose` wants may slot a part | unit test B29 |
| 2026-09-30 | D43 | quoted ids; `roledom#id` form | census anchor check B30 |
| 2026-09-30 | — | ScreenLocked error; `exists` means ≥ 1 match | live finding B31; message bubbles repeat |
| 2026-09-30 | D33 | activation is best effort; intents check "page/window open", not "frontmost" | E3 (§1.1b, B32) |
| 2026-09-30 | D20 | emails are scrubbed from digests and JEV criteria unless the task contains them | a live digest carried an account email |
| 2026-09-30 | D15 | flat schema is the default | E6: anyOf refused, "compiled grammar is too large" |
| 2026-09-30 | D40 | plain-word app names ("space", "mail") count only in an app phrase or when capitalized; the frontmost screen goes to Opus only when the task doesn't name its own target or points at the screen | first live planner task (§1.1b): a false "Space" app match and ~1.8k tokens of an unrelated page |
| 2026-09-30 | D42 | "my <site>" uses the last used browser (highest window in the z-order), then the default browser | a signed-in session lives in the browser the user actually uses |
| 2026-09-30 | D19 | approval card before every irreversible action: type first, read back, ask, then send; no terminal → native dialog (2 min timeout = no); nobody to ask → blocked | your request: ask before sending in WhatsApp |
