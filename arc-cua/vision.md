# Vision: Opus 5.5 + JEV + the AX codex

**Date:** 2026-09-30
**Inputs:** arc-cua @ `57512d4` (plus local changes), the AX codex in `../Ax_analysis/codex/` (71 laws, playbook, 24 app files), public info on TypeSafe JEV.

---

## The one-line idea

**Opus 5.5 plans the task, JEV picks each click, the codex does everything that doesn't need a model, and every success turns into a replay that needs no model at all.**

---

## 1. What we already have

**arc-cua** is a fast executor. A planner hands it a bounded subtask (goal, inputs, verification, constraints). arc-cua reads the screen (AX + local OCR), builds a list of legal actions, asks JEV which one to take, runs it, waits for the UI to settle, and repeats until it returns `SUBTASK_COMPLETE`, `BLOCKED`, or `NEEDS_AGENT`. The planner is on purpose left out of the package.

**JEV** (TypeSafe's "System One" model) doesn't write text. You send it a state plus multiple-choice questions, and it answers all of them in one parallel pass with calibrated probabilities. The claims: 70–500 ms per call, $0.042 per million input tokens, output free. Its known weak spots are counting, dates, literal reading, and large irrelevant state. It's in early access behind a waitlist. arc-cua already asks for the operation, the target, the input key, and the key/hotkey/scroll choice in one call.

**The codex** is what we learned from 24 real apps' AX trees: 71 laws, each with a rule you can code, a 7-step playbook (READY, PICK-WINDOW, FIND, ACT, VERIFY, CLASSIFY, ESCALATE), and a per-app knowledge file for each app. None of it needs a model.

**What's missing** is the planner on top, a memory of what already worked, and the codex's knowledge inside arc-cua's perception layer.

---

## 2. The pipeline

```text
user: "send the design doc to Priya on WhatsApp"
        │
        ▼
┌─────────────────────────────┐
│ ROUTE STORE (no model)      │  known task? → replay steps, check each step in code
│ intent match, ~50 ms        │──── hit ──────────────────────────────┐
└──────────────┬──────────────┘                                        │
               │ miss                                                  │
               ▼                                                       │
┌─────────────────────────────┐                                        │
│ OPUS 5.5 — planner (1 call) │  splits the task into bounded subtasks │
│ writes goal, inputs,        │  and turns "done" into typed checks    │
│ constraints, typed checks   │                                        │
└──────────────┬──────────────┘                                        │
               ▼                                                       │
┌─────────────────────────────┐                                        │
│ arc-cua executor            │                                        │
│  observe ← codex READY,     │                                        │
│            PICK-WINDOW      │                                        │
│  action space ← codex ACT   │                                        │
│  JEV picks op + target      │  ~0.1–0.5 s per step                   │
│  act → settle               │                                        │
│  check ← codex VERIFY       │                                        │
└──────┬───────────────┬──────┘                                        │
       │ done          │ NEEDS_AGENT / BLOCKED                         │
       │               └──► back to Opus (replan or ask the user)      │
       ▼                                                               ▼
  save the trace as a route  ─────────────────────────────►  done, checked in code
```

**Who does what:**

| Layer | Model | Called | Job |
|---|---|---|---|
| Route store + codex | none | every step | window picking, tree readiness, element lookup, legal actions, checks, replay |
| JEV | TypeSafe System One | once per step, only when no route exists | pick the next operation and target from a legal list |
| Opus 5.5 | frontier LLM | once per task, plus on escalation, plus offline | plan, write inputs and checks, handle stuck cases, turn traces into routes |

This is the three-tier setup from the atree notes, except **JEV fills the "local SLM" slot.** It's not local, so there's still a network round trip. But it's close to local-model speed and it can't make up text, which is the property we wanted from a small model anyway.

---

## 3. Where the codex plugs into arc-cua

These are specific. Each one is a real mismatch between what arc-cua does today and what the codex measured.

### 3.1 Cleaner action space for JEV (biggest accuracy win)

JEV is weak at "large irrelevant state" and can only pick from what we offer. Today arc-cua offers too much:

- **Every settable AppKit text field gets `TYPE_TEXT` and `SET_VALUE`.** LAW-ACT-8: 99.7% of AppKit text fields say AXValue is settable, and most of them are labels. One Finder capture had 765 filename labels; Keynote's navigator had 310. arc-cua offers all of them to JEV as typing targets. Fix: only offer text entry when the field can take focus (AXFocused settable). In one Finder capture that cut 765 candidates to 0 and kept every real input (Calendar 14/14, Reminders 14/16).
- **`CLICK` is offered on anything with `AXPress` or `AXShowMenu`.** LAW-ACT-6: in web stacks the context-menu action sits on 74–100% of static text and groups. So in Electron and WebKit apps nearly every text node becomes a click candidate. Fix: don't count `AXShowMenu` alone as clickable.
- **Disabled controls.** LAW-ACT-7: AppKit, Chromium, and Electron keep the press action on disabled buttons. arc-cua already filters on `enabled`, which is right; keep it that way.
- **Toggles, lists, dropdowns.** LAW-ACT-2/3/4: checkbox/radio/switch always toggle, `Select` lives on the list and not the item, and dropdowns expand. arc-cua can map these to cleaner operations.

**Expected effect:** much shorter candidate lists, so JEV has fewer wrong options to choose from. We can measure this directly: count candidates per snapshot before and after on the existing examples.

### 3.2 Seeing the right window, at the right depth

- **Window.** arc-cua reads `AXFocusedWindow` of the frontmost app only. LAW-WIN-6 plus the READY ladder handle the cases that breaks on: 80.7% of listed windows are ghosts, hidden windows show only a thumbnail proxy, and Finder can list 9 ghosts and no real window.
- **Depth.** arc-cua walks to depth 18. LAW-STR-3: native apps never go below depth 9, so 10 is enough and cheaper. Web content goes much deeper; LAW-LIFE-3 has the forced trees reaching depth 12–30 (Notion 30). So depth 18 cuts off part of Electron UIs. Fix: depth 10 for native, 30+ inside the webarea.
- **Background reading.** LAW-LIFE-4: native apps give a full tree without being frontmost. arc-cua could read the target app without stealing focus, and only activate before a physical click.
- **Give up early where AX is useless.** LAW-LIFE-8: Telegram serves a 1-node tree no matter what. Detect it on the first read and go straight to OCR.

### 3.3 Faster observes

`LATENCY_IMPROVEMENT.md` already found the real cost: 14 AX round trips per node (Finder 4.8 s per walk). The codex adds two cheap cuts:

- **Stop at depth 10 in native apps** (LAW-STR-3). Nothing interactive has been seen below depth 9 in about 2,700 native elements.
- **Collapse wrapper chains** (LAW-STR-4/5). Electron trees are about 54% unnamed wrapper groups. Collapsing them loses nothing and shrinks what goes to JEV.

### 3.4 Checks that don't trust the model

Today `verification` is a list of sentences, and JEV decides `SUBTASK_COMPLETE` by reading them. That's exactly its weak spot (literal reading, dates, counting). The explainx write-up of TypeSafe's own browser agent says the same: verify completion separately, don't trust `DONE`.

**Change:** Opus 5.5 writes each check as a typed postcondition (`title_matches`, `value_equals`, `node_exists`, …) from atree's `core/postconditions.py`. Code checks it using the codex VERIFY recipes: look at `value`, not `name` (LAW-TXT-7); a missing value key means empty (LAW-TXT-1); a toggle's state is `'0'`/`'1'` (LAW-TXT-10). JEV's `SUBTASK_COMPLETE` becomes a hint that triggers the code check, not the final word.

### 3.5 Memory: routes

arc-cua forgets everything between subtasks. Add the route store from atree. When a subtask finishes and its typed checks pass, save the app, the goal signature, and the steps as selectors, **never ref ids** (LAW-ID-8: refs die with the snapshot). Use the codex resolver chain (LAW-ID-12) so replay finds elements again. Next time the same kind of task skips Opus and JEV entirely.

---

## 4. Rough latency budget

These are estimates, not measurements. JEV's numbers are TypeSafe's claims.

| Case | Opus | JEV | Estimated total |
|---|---|---|---|
| Known task (route hit) | 0 calls | 0 calls | **2–4 s**, limited by the app's own UI speed |
| New task, known app | 1 call (~3–8 s) | 4–6 calls (~0.1–0.5 s each) | **~8–15 s** |
| New task, stuck midway | 2–3 calls | 6–10 calls | 15–30 s |

Per step without a route: observe (0.1–0.3 s after the latency fixes, native apps) + JEV (0.1–0.5 s) + act and settle (0.2–0.7 s) ≈ 0.5–1.5 s.

The main lever over time is the route hit rate, not model speed.

---

## 5. Build order

Each step can be measured on its own using the existing `examples/` (Settings, Spotify, WhatsApp).

1. **Action-space cleanup** (§3.1). Small change in `macos_ax.py`. Measure candidates per snapshot and JEV's pick accuracy before and after.
2. **Latency plan phases 1–5** from `LATENCY_IMPROVEMENT.md`, plus depth 10 for native apps (§3.3).
3. **READY + PICK-WINDOW** in `observe()` (§3.2): window picking, depth by framework, early OCR fallback for opaque apps.
4. **Typed checks** (§3.4). Add a typed `checks` field to `Subtask` next to the prose `verification`, and check it in code.
5. **Opus 5.5 planner.** A thin loop outside the package (arc-cua keeps the planner outside on purpose). It writes subtasks and handles `NEEDS_AGENT`/`BLOCKED`.
6. **Route store.** Save passing traces; replay them with no model; if a replay step fails its check, fall back to JEV for that step.
7. **Learning loop.** Outcomes feed the atree ledger. Opus offline turns repeated fixes into codex updates.

Steps 1–3 need no new models and should make the current JEV loop faster and more accurate right away.

---

## 6. Open questions to test first

1. **Does arc-cua see Electron content today?** The codex found the Electron "husk" was agent-desktop's depth-10 cap, not a missing `AXManualAccessibility` handshake (LAW-LIFE-1). arc-cua walks AX directly at depth 18 with a 1,200-element cap. Run `examples/macos_ax_probe.py` on Notion and Discord and compare with the codex counts (Notion forced: 1,004 nodes, depth 30).
2. **JEV's real speed and accuracy on our snapshots.** TypeSafe's claims haven't been measured on arc-cua state. Time each call and log wrong picks on the three examples.
3. **How much does §3.1 shrink the candidate lists?** One script over the codex captures can answer this before touching arc-cua.

---

## 7. Risks

- **JEV is early access and closed.** If TypeSafe changes pricing or access, the per-step layer goes with it. Keep `DecisionPolicy` swappable (it already is) and keep a local-model policy as a backup.
- **Privacy.** JEV gets element names and values, which include real message previews, contact names, and file names (the codex saw this in WhatsApp, Finder, and Calendar). That data leaves the machine. Consider masking content-region text before sending (atree's registry already has a selectors-not-content rule), and ask for the user's consent.
- **The codex is not verified.** 71 laws, each computed by one analyst over one capture per app, often of a splash or login screen. The adversarial check never ran, and two topics (geometry, fingerprint) are missing. Treat the laws as strong defaults and log when they fail.
- **Network round trips.** JEV is a cloud call. Per-step latency depends on the network, not just the model.
- **Opus cost.** One call per new task is fine. Opus in the inner loop would bring back the problem arc-cua exists to solve, so keep it out.

---

## Sources

- JEV: [TypeSafe blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev), [System One docs](https://docs.typesafe.ai/concepts/system-one), [MarkTechPost coding guide](https://www.marktechpost.com/2026/09/23/a-coding-guide-to-typesafe-ai-jev/), [eesel latency test](https://www.eesel.ai/blog/jev-ultrafast), [explainx on jev-ultrafast](https://www.explainx.ai/blog/jev-ultrafast-browser-use-typesafe-2026)
- Codex: `../Ax_analysis/codex/laws.md`, `playbook.md`, `apps/*.json`
- arc-cua: `README.md`, `docs/internals.md`, `LATENCY_IMPROVEMENT.md`, `src/arc_cua/backends/macos_ax.py`, `src/arc_cua/policies/typesafe.py`
