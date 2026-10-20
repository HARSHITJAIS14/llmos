# atree v2 — the plan

Status: plan only. No code yet. This file is the design we agreed on.

The goal is one thing: **make a brand-new task fast.** Not a cached task. A
task we have never run, on an app we may not have seen. That is the case that
hurts while testing, and it is the case v1 is slow at.

---

## 1. What we measured

All numbers below are from this machine, not guesses.

| thing | time |
|---|---|
| AX skeleton snapshot (Finder) | 80–90 ms |
| full tree snapshot (Finder) | 80 ms |
| raw Rust binary start | ~20 ms |
| Node shim on top of the binary | +30 ms |
| one full observe cycle | **~100 ms** |
| one frontier model call | **3,000–8,000 ms** |

Tree sizes across the 22 apps that captured in `Ax_analysis/census_summary.json`:

| | median | worst |
|---|---|---|
| skeleton | 1,490 B (~370 tokens) | Firefox 6,616 B |
| full tree | 11,593 B (~2,900 tokens) | Finder 310,836 B (~78k tokens) |

Tree quality across those 22 apps:

- 18 gave a substantive skeleton
- 3 gave a thin one: Telegram 397 B, Notion 749 B, Claude 750 B (all Electron)
- 1 failed: Discord, PERM_DENIED
- 6 apps never launched during the census (WhatsApp, Postman, Canva, VSCode,
  Cursor, OBS) — so 18/22 is an incomplete number and Cursor/VSCode will
  likely drag it down. Re-run the census before trusting it.

**Conclusion: the local side is free. Roughly 100% of our wall clock is the
model call.** Every optimisation must be aimed at the model call, or it is a
waste of time.

Two corollaries we should stop arguing about:

- **We cannot shrink our way out.** The median skeleton is ~370 tokens.
  Sending it costs nothing. Prompt caching also buys us little at that size.
- **Output tokens are the real cost of a call.** Input is 370 tokens. A plan
  with reasoning is 1,000–1,500 tokens out. At 50–100 tok/s that is 10–20
  seconds of pure generation.

## 2. What is actually wrong with v1

v1 exposes **7 fine-grained tools**: `ax_recall`, `ax_observe`, `ax_find`,
`ax_open`, `ax_guide`, `ax_type`, `ax_do`.

Each tool call is one model turn. The WhatsApp route is 6 steps. That is 6+
turns at 3–8 s each. **30–50 seconds, of which ~600 ms was real work.**

The tool schemas in `mcp/server.py` are 5,688 bytes (~1,422 tokens), re-sent
on every turn.

**MCP is not the problem.** Its wire is JSON over stdio, about 1 ms. If we
replace MCP with gRPC or a raw socket we will still make 6 round trips and it
will still take 30 seconds. The problem is **granularity**, not transport.
Fixing the transport is the wrong project.

Also wrong in the original framing, for the record:

- "We can't verify with the AX tree." We can, and we already do.
  `core/vision.py` says it itself: *"Vision never enters the verification
  path; it enters the FAILURE branch of the verification path."* There are 5
  typed postconditions in `core/postconditions.py`.
- "Parallelising fixes the infinite loop." It does not. It makes us loop
  faster. Loops need a loop detector, which is a separate piece of work
  (see §8).

## 3. The core idea

**Stop making the model the loop.**

Today the model decides, we act, the model decides again. One decision per
round trip. Instead: the model writes a plan once, and a local process runs
the whole plan, checking itself as it goes, and comes back once.

The model's job shrinks to planning. Our job grows to executing and verifying.

```
frontier  ──one turn──▶  plan: 10 steps, terse, each with expected result
                                    │
                        ┌───────────▼────────────┐
                        │  atree_v2 runtime      │  long-lived process
                        │  · warm AX handle      │
                        │  · VLM weights resident│
                        │  · loop per step:      │
                        │      resolve           │
                        │      act               │
                        │      verify (ladder)   │
                        │      next              │
                        └───────────┬────────────┘
                                    │ only when reality disagrees
frontier  ◀──one turn──  "diverged at step 4, here is the state"
```

Target for a 10-step new task: **~4 s**, down from ~50 s. The win comes from
2 model calls instead of 10, with short outputs, from a faster model.

## 4. The runtime process

One long-lived Python process. This is the main new thing to build.

It owns:

- **A warm AX handle** via the C-ABI cdylib in
  `agent-desktop/crates/ffi/`. v1 calls `subprocess.run` on the CLI for every
  single action (`core/snapshot.py:28`), and worse, through
  `npm/bin/agent-desktop.js`, which boots Node just to spawn the Rust binary.
  That is ~50 ms of nothing per call. In-process it is a function call.
- **Local VLM weights, resident.** Loaded once, never unloaded. Do not put
  the VLM behind MCP or an HTTP server. A hop to our own machine is a hop we
  do not need.
- **The current snapshot and its diff state**, so `core/axdiff.py` can diff
  against the last look without re-reading from disk.
- **The registry connection** (`core/registry.py:connect`), kept open.
- **The step ledger for the current task** — what we tried, what happened.

Why one process and not a fresh script per task: warm AX, warm weights, warm
DB, warm diff state. Each of those is 20–500 ms we stop paying repeatedly.

Interface: it reads a plan and writes a result. Start with stdin/stdout JSON
lines. Do not design a protocol. If we later want a socket, add one.

## 5. The plan schema

This is the contract between the frontier model and the runtime. Keep it
brutally short — every field costs output tokens, and output tokens are our
main cost.

One step:

```json
{
  "i": 4,
  "cmd": "click",
  "target": {"ref": "@s8f3k2p9:e12"},
  "expect": {"kind": "node_exists", "expect": {"role": "textfield"}, "scope": "..."},
  "risk": "safe",
  "grounding": "ax"
}
```

Fields, and why each exists:

- `i` — step index. Needed so a divergence report can name a step.
- `cmd` — one of the `agent-desktop` command names. The real list is long
  (`snapshot`, `find`, `click`, `type`, `press`, `focus`, `set-value`,
  `clear`, `select`, `toggle`, `check`, `uncheck`, `expand`, `collapse`,
  `scroll`, `scroll-to`, `launch`, `focus-window`, `list-windows`, and the
  `mouse-*` / `drag` / `hover` family which need `--headed`). Give the model a
  short allowlist per task, not all 54.
- `target` — either `{"ref": "@snapshot:eN"}` for an AX ref, or
  `{"text": "Send", "role": "button"}` to resolve by text, or
  `{"point": [x, y]}` for a physical click. Prefer refs.
- `expect` — a `core/postconditions.py` Postcondition, serialised. This is the
  branch predictor. Without it we cannot tell success from failure locally,
  and we are back to asking the model.
- `risk` — `safe` or `irreversible`. Drives §7.
- `grounding` — `ax` or `pixel`. Tells the runtime whether to expect the AX
  tree to have the target, or to go to the VLM. Model sets it from the
  skeleton; runtime overrides if the tree surprises it.

The whole plan:

```json
{
  "plan_id": "p7",
  "from_snapshot": "s8f3k2p9",
  "app": "WhatsApp",
  "goal": "send 'on my way' to Ravi",
  "steps": [ ... ]
}
```

`from_snapshot` is load-bearing. See §9.

Hard rules for the model's output:

- No prose. No explanation. No restating the goal.
- Postconditions must use the 5 existing kinds only: `node_exists`,
  `node_absent`, `value_equals`, `value_contains`, `title_matches`. Anything
  else is not checkable locally.
- A 10-step plan should be around 150 output tokens. If it is 1,000, the
  schema or the prompt is wrong.

## 6. The verification ladder

We already have this. v2 keeps it and adds one rung consumer. Rungs, cheapest
first, and each may only fire when the one below was inconclusive:

| rung | what | cost | where it lives |
|---|---|---|---|
| 0 | AX postcondition on the current tree | ~0 ms (tree in hand) | `postconditions.evaluate` |
| 1 | AX re-query (fresh snapshot, then evaluate) | ~90 ms | `postconditions.evaluate_live` |
| 2 | region pixel-hash delta | free, no model | `vision.region_changed` |
| 3 | local OCR via Vision.framework | free, no model | `vision.ocr_region`, `core/ocr.swift` |
| 4 | bounds-cropped image → **local VLM** | ~300–500 ms | new; crop from `vision.capture_region` |

**Rung 4 is the whole point of v2.** Today rung 4 says: *"in Claude Code the
agent itself is the VLM — this module produces the crop, the agent Reads the
file."* So every rung-4 escalation is a full frontier round trip, 3–8 s. Put a
small local model there and it becomes ~400 ms.

This one change is worth doing on its own, before any of the plan/runtime
work. It is independent and it is the highest ratio of win to effort.

Expected mix, to be measured: ~80% of steps settle at rung 0–1, ~20% escalate.
If the real escalation rate is much higher than that, the postconditions the
model writes are bad and that is a prompt problem, not an architecture problem.

## 7. Why cropping is the trick

Image tokens dominate VLM prefill. That is the entire reason a local VLM can
be fast here.

- full screen at 1568 px longest edge ≈ 1,000–2,000 image tokens
- a 400×200 bounds crop ≈ 50–100 image tokens

That is 10–20x less prefill, which is why the estimate is ~400 ms and not
2 s. And we already produce the crop: `vision.capture_region` with
`CROP_PAD_PX = 20`, using `screencapture -x -R`.

This AX→crop→VLM path is our real structural advantage over pixel-only CUAs.
Pixel-only agents have to look at the whole screen because they have no tree
to tell them where to look. We do.

**The exception: qt-opaque apps report `bounds: None`.** We cannot crop what
has no bounds. OBS and friends need a full-resolution capture and will be
slower. Price them separately and do not let them set expectations for the
rest.

Where the VLM goes, and where it does not:

- Target is in the AX tree → **act via AX ref**. Headless, deterministic,
  ~100 ms, zero coordinate error. No VLM at all. This is the main path.
- Target is not in the tree → **crop + VLM grounds it** → coordinate click.
  This is for the archetypes where the tree fails: truncated Electron
  webareas (Telegram, Notion, Claude in our own census), qt-opaque, canvas.

The VLM is a fallback for grounding and a fallback for verification. It is
never the default.

## 8. Speculation, squash, and loops

The runtime runs the plan optimistically. It does not stop to ask permission
between steps.

**Effective step cost** ≈ `F / k_eff + s`, where `F` is the frontier call,
`s` is the local step (~100–400 ms), and `k_eff ≈ min(k, 1/p_miss)`.

`p_miss` — the chance a predicted post-state is wrong — is the number that
decides everything. At `p_miss = 0.3`, `k_eff ≈ 3.3` no matter how deep we
plan. At `0.1`, `k_eff ≈ 10`. **Measure `p_miss` before tuning anything else.**

Good news: a wrong guess costs ~100 ms of wasted local action, not a model
call. So optimistic execution is cheap even when it is wrong.

**Squash.** On the first postcondition failure: stop. Do not continue the
plan. Return the divergence report: step index, what we expected, what the
tree actually shows (an `axdiff` against `from_snapshot`), and the last known
good step. The frontier replans from there.

**Loop detection** — this is the fix for the infinite-loop problem, and it has
nothing to do with speed:

- Hash `(state_signature, action)`. `axdiff.identity_key` already gives stable
  per-node identity, so a whole-tree signature is easy to derive.
- If we revisit a pair we have already tried, we are cycling. Stop.
- Cap: 3 attempts per step, `k` steps per plan, and a global step budget per
  task. Hard fail with a reason, never silently retry forever.
- Ask the model for a **progress note** per step, not just a post-state, so we
  can tell "moving" from "moving toward the goal".
- Mark each command's idempotency. Clicking a button twice may open two
  dialogs. Retry is only safe for idempotent commands — note that
  `agent-desktop` already flags `check` / `uncheck` as idempotent in its own
  help text, which is a hint the distinction matters.

## 9. Stale plans

The plan was written against snapshot `s8f3k2p9`. By step 4 the world has
moved. That is fine for speculation, but it must be checked, not assumed.

- Every plan carries `from_snapshot`.
- Before each step, diff current state against the plan's snapshot with
  `axdiff.diff`. If the step's target or scope has moved or vanished, squash
  rather than clicking the wrong thing.
- `axdiff.resolve(path, sidecar)` is how a structural path gets re-resolved
  after the tree shifts.

This check is local and free. There is no reason to skip it.

## 10. Risk gating

Speculation must stop at actions we cannot undo. This is a correctness rule,
not a performance tradeoff.

- `risk: "safe"` → act, verify async, keep going. Squash if verification later
  fails.
- `risk: "irreversible"` → verify the previous step **synchronously** before
  acting, no speculation past it, and optionally require a human gate.

Irreversible means: send, delete, submit, pay, overwrite, move, quit-without-
saving. Borrow the taxonomy from `fazm/acp-bridge/src/approval-gate.ts` — it
gates on `edit` / `delete` / `move` / `execute` with three modes (`off`,
`destructive`, `always`) and a timeout flush so a pending gate can never hang
forever. That file is 225 lines with zero imports; the logic ports cleanly.

The WhatsApp route already has the right instinct at step 4: a hard
`RECIPIENT_MISMATCH` gate before any typing. Keep that pattern and generalise
it — a recipient check is just an irreversible-action precondition.

## 11. Model tiering

Stop sending "read these 30 elements and pick which to click" to a flagship.

- **Planning a novel task**: a mid model is probably enough. Try Sonnet.
  Reserve the flagship for when a plan fails twice and we are genuinely stuck.
- **Simple next-step decisions**: Haiku, or the local model.
- **Local VLM**: grounding and rung-4 verification only.

Expect 2–4x on latency from tiering alone. Measure accuracy per tier on the
same task set before committing — the point is that this task shape probably
does not need flagship reasoning, but that is a claim to test, not assume.

Local model selection criteria, when we get there:

- **Constrained decoding is mandatory.** The 20–30 token result schema
  (`done` / `failed` + why + any new info) must be schema-enforced, for speed
  and for not having to parse prose.
- **Prefix / KV caching**, so the stable system prompt is not re-prefilled.
- **Tolerant of small inputs**, because cropping is the whole lever.
- **One set of weights, two prompts** for executor and verifier. A 7B at fp16
  is ~14 GB; we will not fit two models alongside a browser.

Not yet evaluated: FocusUI, Tzafon/Northstar-CUA-Fast, arXiv 2603.12823. Need
measured prefill throughput at crop-sized inputs before any of them goes in the
budget. Do not build a latency plan on a number from a README.

## 12. What happens to MCP

Keep `mcp/server.py`. It is the reason Cursor, Gemini CLI, Codex and Claude
Desktop can use this at all. But collapse it:

**7 tools → 1 tool.**

```
ax_run_plan(plan)
```

- One model turn per plan instead of one per action.
- Tool schema drops from ~1,422 tokens to maybe 150.
- Every host we support keeps working.

Change the granularity, not the protocol.

Optionally keep `ax_recall` as a second tool, since it is genuinely a
pre-flight and its answer changes whether we plan at all. Two tools, not
seven.

## 13. What we keep from v1

Almost all of the thinking. v2 is a re-plumbing, not a rewrite.

- `core/postconditions.py` — the 5 typed kinds, `evaluate`, `evaluate_live`.
  Unchanged. This is the branch predictor.
- `core/vision.py` — the ladder, `capture_region`, `region_hash`,
  `region_changed`, `ocr_region`, `text_present`, `diagnose`. Gains a real
  rung-4 consumer.
- `core/axdiff.py` — `identity_key`, `flatten`, `diff`, `resolve`. Now also
  used for stale-plan checks and loop signatures.
- `core/registry.py` + `registry/registry.db` — app profiles, elements,
  routes, confidence.
- `core/recall.py` — L1/L2/L3/miss. Still worth calling first; it just is not
  our cold-path answer.
- `core/ledger.py` — `MIN_EVIDENCE = 2`, `REFUTE_AFTER = 2`, `can_promote`.
  The learning-promotion discipline stays.
- The archetype references (`catalyst.md`, `electron.md`, `qt-opaque.md`,
  `browser.md`, `dialogs.md`, `rich-text.md`). These directly inform the
  `grounding` field.
- `hooks/` — `verify_hook.py`, `state_diff_hook.py`, `registry_hook.py`,
  `learn_hook.py`. These enforce declare-then-act. In v2 the runtime enforces
  it in-process instead, which is better, but the rules are the same.
  Note: the current hook has false positives — it fired "Mutating action ran
  with NO declared postcondition" on read-only `status` calls and on file
  writes during this session. Worth fixing whether or not v2 happens.

## 14. Build order

Ordered by win-per-effort. 1 and 2 are independent — either can ship alone.

1. **Kill the Node shim.** Point `core/snapshot.py` at
   `agent-desktop-darwin-arm64` directly instead of `npm/bin/agent-desktop.js`.
   Saves ~30 ms per call. Ten minutes of work. Do it today.
2. **Local VLM at rung 4.** Feed it the crop `vision.capture_region` already
   makes. Turns a 3–8 s frontier escalation into ~400 ms. Needs no plan
   schema, no runtime, no MCP change.
3. **Plan schema + executor loop.** The §5 contract, plus a loop that walks it
   using the existing postconditions. This is where the 10x lives.
4. **Collapse MCP to `ax_run_plan`.** Small change, large effect, and it is
   what makes 3 actually pay off end to end.
5. **Long-lived runtime process holding the FFI handle.** Kills the remaining
   ~20 ms per call and gives the VLM weights and the AX handle somewhere warm
   to live.
6. **Loop detector + risk gate.** Correctness, not speed. Do not ship 3–5
   without at least the step budget in place.
7. **Streaming plans.** Emit one step per line and fire step 1 as its line
   lands. Cuts time-to-first-action to ~1 s. Mostly a perceived-speed win, but
   perceived speed is half the complaint.
8. **Model tiering.** Cheap to try, needs an accuracy check.

## 15. Numbers to get before tuning

We have the local numbers. We do not have these, and they decide the design:

- **`p_miss`** — how often is a predicted post-state wrong? Sets useful
  speculation depth. Most important number.
- **Rung distribution** — what fraction of steps settle at rung 0–1 vs
  escalate to 4? Sets how much the local VLM matters.
- **AX-addressable rate** — what fraction of targets have a usable ref?
  Sets how often we need pixel grounding. Re-run the census first; the
  current 18/22 is missing 6 apps including Cursor and VSCode.
- **Local VLM prefill at crop size** — real tokens/sec on real crops on this
  machine. The ~400 ms figure is an estimate and the whole budget leans on it.
- **Frontier plan output length** under the terse schema. Target ~150 tokens
  for 10 steps.
- **Accuracy per model tier** on a fixed task set.

## 16. Risks

- **The frontier cannot plan a novel app blind.** If `p_miss` turns out very
  high, `k_eff` collapses toward 1 and we are back to per-step round trips.
  Mitigation: L3 archetype context in the prompt, and accept shallower plans
  (k=3) rather than none.
- **Bad postconditions.** The whole scheme rests on the model writing checkable
  `expect` fields. If it writes vague ones, everything escalates to rung 4 and
  we lose the win. Mitigation: constrain to the 5 kinds, validate the plan
  before executing it, reject and re-ask on a malformed plan.
- **Local VLM slower than hoped.** If prefill at crop size is 1.5 s, not
  400 ms, rung 4 is much less attractive and OCR at rung 3 has to carry more.
- **Speculation on irreversible actions.** A misprediction here is a real bug,
  not a lost 100 ms. §10 is not optional.
- **One process, one point of failure.** A crashed runtime loses warm state
  mid-task. Needs a clean restart path that does not lose the plan.

## 17. Deliberately not doing

- Not replacing MCP with a new protocol. The transport is ~1 ms.
- Not shrinking the tree further. The median skeleton is ~370 tokens.
- Not leaning on prompt caching. Too small a prefix to matter.
- Not chasing L1 route hit rate as the answer to cold-path speed. Routes are
  great for repeat work and useless while testing new tasks, which is the
  case we are fixing here.
- Not building a new verification system. We have one; it needs a rung-4
  consumer, not a rewrite.
