# ATree → `atree`: restructuring the harness as a Claude Code plugin

**Status:** proposal, pre-implementation
**Date:** 2026-08-29
**Supersedes:** `LLM_OS/ATree_tool/` (stashed at `stash@{0}` on `claw_integration`)

---

## 1. The thesis

We built a harness. Roughly 90% of it is a re-implementation of things Claude Code
already ships — an agent loop, context management, tool dispatch, model plumbing,
retry logic, user-clarification pauses. The remaining 10% is genuinely ours and
genuinely hard:

- the macOS AX-tree domain knowledge (four app archetypes, the click paradox,
  focus leakage, the Electron veil)
- state-diff as a token-compression strategy
- postcondition-based verification
- compiled routes (discover once, replay in one turn)

Right now that 10% is buried inside the 90%, coupled to it, and untestable on its own.

**The restructure deletes the 90% and makes the 10% the product.**

That is the whole argument. Everything below is mechanism.

---

## 2. Why a plugin, and why Claude Code / Codex conventions specifically

### 2.1 The harness we wrote is a worse version of one we already have

Concretely, here is the current architecture mapped onto primitives that already exist:

| What `ATree_tool` does today | Primitive that already does it | What we delete |
|---|---|---|
| `utils/prompts.md` — hand-pasted cognitive-loop prompt | **Skill** — auto-invoked on desktop-automation intent | manual prompt injection |
| `.agents/AGENTS.md` — 90-line always-on monolith | `AGENTS.md` (thin) + **skill `references/`** | permanent token tax |
| `learnings/learnings.md` — 163-line always-on monolith | **skill `references/`**, loaded per archetype | permanent token tax |
| `utils/dfs_tree.py` — subprocess + JSON marshalling shim | **MCP server**, or plain Bash to the CLI | glue code |
| `utils/harness_logger.py` — every task calls `log_action()` | **`PostToolUse` hook** — fires automatically | per-task logging boilerplate |
| `success = ...` at the end of each task script | **`PostToolUse` hook** that can *block* (exit 2) | hand-rolled, unenforced checks |
| the LangGraph state machine (planned) | **Claude Code is the loop** | an entire orchestrator |
| `tasks/*.py` — verified compiled routes | **slash commands** (`commands/*.md`) | custom dispatcher |
| "STOP and ask the user" disambiguation rule | **`AskUserQuestion`** | custom pause/resume |
| API keys, `.env`, dotenv, budget, retries | the host CLI | config surface + a leaked key |

Every row is code we maintain that someone else maintains better, tests harder,
and ships to more platforms than we do.

### 2.2 Hooks are the actual unlock — they solve goals 2, 3 and 4 at once

This is the non-obvious part, and it is why "plugin" beats "repo of scripts."

A **`PostToolUse` hook** fires deterministically after every matching tool call.
It costs zero model turns, cannot be forgotten by a task script, and — critically —
its stdout is fed back into the model's context.

That single mechanism fixes three of our four stated goals:

- **Token usage.** The hook computes the state diff and injects *the diff* instead
  of the snapshot. Today `state_diff.py` writes a log file that no model ever reads,
  which is why it is currently a debugging artifact rather than a token optimization.
  As a hook, the compression is applied at exactly the point where it pays.
- **Fewer turns.** Every check moved into a hook is a turn the model does not spend.
  Auto-diffing, auto-verification, and auto-focus-management become free.
- **Verification.** A hook that exits `2` with a message on stderr *blocks* and feeds
  the failure back to the model. That is enforcement. `success = matched is not None
  or folder_name in str(s4)` is a boolean nobody acts on — and one that reports
  success when the open failed, because it substring-matches the path still sitting
  in the file picker's own text field.

We cannot get any of this from a Python harness without rebuilding the harness.
We get all of it from ~60 lines of `hooks.json` plus two scripts.

### 2.3 Why the `AGENTS.md` / MCP conventions make this portable, not lock-in

The reasonable objection is: "doesn't building on Claude Code lock us to Claude Code?"

No — if we structure it correctly. There are three portability tiers, and we design
around them deliberately:

| Tier | Content | Claude Code | Codex | Gemini CLI |
|---|---|---|---|---|
| **Knowledge** | `AGENTS.md`, archetype references | ✅ | ✅ (native) | ✅ |
| **Tools** | MCP server / `agent-desktop` CLI | ✅ | ✅ | ✅ |
| **Automation** | hooks, skills, slash commands | ✅ | partial | partial |

Tiers 1 and 2 are *industry conventions*, not Anthropic features. `AGENTS.md` is read
natively by Codex. MCP servers load in all three (Codex via `~/.codex/config.toml`,
Gemini via `settings.json`). So the knowledge and the tools — the parts that took
months to learn — are portable by construction.

Only tier 3 is host-specific, and it is the *thinnest* layer: config files and small
scripts wrapping `core/`. Codex and Gemini users get the same knowledge and the same
tools, they just run the verification explicitly instead of getting it automatically.

**We are not betting the domain knowledge on one vendor. We are betting the
convenience layer on one vendor, and that layer is ~500 lines.**

### 2.4 It becomes a distributable artifact

`ATree_tool` is a folder on one laptop. A plugin is:

```bash
/plugin marketplace add harshit/atree
/plugin install atree@atree
```

Versioned, installable, one command for a teammate or a design partner or a YC
reviewer. For a company whose product is *"an agent that can drive your Mac,"*
having the thing be installable in ten seconds is not a nice-to-have.

---

## 3. Target structure

```
atree/
├── .claude-plugin/
│   ├── plugin.json              # name, version, author
│   └── marketplace.json         # so `/plugin marketplace add` works from this repo
│
├── AGENTS.md                    # HOST-AGNOSTIC. Codex + Gemini read this directly.
├── CLAUDE.md                    # thin pointer at AGENTS.md — no duplicated rules
│
├── skills/
│   ├── atree/
│   │   ├── SKILL.md             # the observe → reason → act → verify loop
│   │   └── references/          # CONFIRMED learnings — the only tier in context
│   │       ├── archetypes.md    # INDEX: classify app → load one file below
│   │       ├── electron.md      # Notion, VSCode: DFS drill-down, ghost windows
│   │       ├── catalyst.md      # WhatsApp, Calendar: list-windows quirks, surfaces
│   │       ├── qt-opaque.md     # OBS: bounds:None → semantic AXPress only
│   │       ├── browser.md       # Cmd+L, Cmd+Shift+N, webarea polling
│   │       ├── dialogs.md       # save-panel / open-panel / Cmd+Shift+G
│   │       └── rich-text.md     # HTML → RTF → NSPasteboard
│   └── atree-learn/
│       └── SKILL.md             # promotion rules: candidate→confirmed, route→command
│
├── learnings/                   # UNCONFIRMED. Never loaded into context.
│   ├── ledger.jsonl             # append-only evidence, written by hooks, read by tooling
│   ├── candidates/              # n=1 and n≥2 observations awaiting a repro
│   └── archive/                 # refuted + stale, kept for provenance
│
├── registry/                    # EPISODIC. Queried, never loaded. Local-only.
│   ├── registry.db              # SQLite + FTS5: apps, elements, routes, outcomes
│   └── profiles/<app>/          # per-app surface map + provenance stamp
│
├── commands/
│   ├── ax-discover.md           # run the cognitive loop to find a new route
│   ├── ax-snapshot.md           # skeleton-first inspection
│   ├── ax-learn.md              # batched review: promote corroborated candidates
│   ├── ax-recall.md             # query the registry: what do we know about <app>?
│   └── routes/                  # compiled routes — one turn, no discovery
│       ├── whatsapp-send.md
│       ├── vscode-open-folder.md
│       └── ...                  # the 11 verified tasks, ported
│
├── agents/
│   └── ax-verifier.md           # adversarial subagent: "prove the action landed"
│
├── hooks/
│   ├── hooks.json
│   ├── state_diff_hook.py       # PostToolUse → inject compact diff, not snapshot
│   ├── verify_hook.py           # PostToolUse → check postcondition, exit 2 to block
│   ├── learn_hook.py            # Stop → mine fail→pass transitions into candidates/
│   ├── registry_hook.py         # PostToolUse → deposit every verified interaction
│   └── session_start.py         # SessionStart → load archetype index only
│
├── core/                        # HOST-AGNOSTIC PYTHON — the 10% that is actually ours
│   ├── axdiff.py                # identity-keyed state diff (the fix)
│   ├── postconditions.py        # typed verification primitives
│   ├── routes.py                # compiled-route replay + fallback-to-discover
│   ├── snapshot.py              # skeleton-first capture, drill-down on demand
│   ├── ledger.py                # evidence append/query, promotion + eviction rules
│   ├── registry.py              # element/route store, identity keys, staleness decay
│   ├── recall.py                # L1→L2→L3 lookup chain, the pre-flight for every task
│   └── vision.py                # escalation ladder: pixel-hash → OCR → cropped VLM
│
├── mcp/
│   └── server.py                # optional: agent-desktop MCP wrapper until Phase 4 lands
│
└── tests/
    ├── fixtures/                # salvaged snapshot pairs = regression corpus
    └── test_axdiff.py           # asserts token reduction, not just correctness
```

Two design rules hold this together:

1. **`core/` never imports anything host-specific.** Hooks, commands and MCP are all
   thin wrappers over `core/`. This is what keeps Codex/Gemini viable.
2. **Nothing is always-on except the archetype index.** Everything else is
   progressive disclosure.
3. **Unconfirmed knowledge cannot enter context.** `learnings/` is never read by a
   model; `references/` is. The directory boundary enforces the confidence gate, so
   no one has to remember a rule.
4. **`registry/` is queried, never loaded.** It will grow to megabytes. It is a
   database, and it is addressed like one.

---

## 4. The learning loop: how knowledge compounds

`prompts.md` §6 currently says: *"Upon task completion or failure, update
`learnings/learnings.md` with any new quirks."* That single instruction is why we have
a 163-line monolith of unverified assertions with no provenance. It is an
append-on-vibes loop — no gate, no dedupe, no eviction. Left as-is it will refill
exactly the context budget Phase 3 frees up, and we will have moved backwards.

So the requirement is not *"let learnings grow."* It is:

> **Learnings grow only on evidence, and shrink on contradiction.**

### 4.1 The insight: verification already produces the evidence

We do not need a new subsystem for this. The Phase 4 verification hook emits a
pass/fail for every postcondition on every action. That stream **is** the evidence
base — every fail→retry→pass transition is a datapoint saying *"strategy A did not
work on app X, strategy B did."*

Learning accumulation is therefore an **aggregation over the verification log**, not
an act of authorship. This distinction matters more than it looks. We never ask the
model *"what did you learn?"* — that question invites confident, plausible folklore
from a single observation, which is precisely how the current monolith got written.
We ask instead: *"which claims does the ledger now support?"*

### 4.2 Three tiers, three gates, one context boundary

This mirrors the `experiments/ → tasks/` promotion we already trust and already use.

| Tier | Gate to reach it | Lives in | Loaded into context? |
|---|---|---|---|
| **observed** | n=1, written automatically by the `Stop` hook | `learnings/candidates/` | ❌ never |
| **corroborated** | n≥2 on *independent* runs | `learnings/candidates/` | ❌ never |
| **confirmed** | corroborated **and** has a repro — a fixture pair, or a route that regresses without it | `skills/atree/references/` | ✅ on demand |
| **refuted / stale** | 2 verification failures, or provenance older than current `agent-desktop` | `learnings/archive/` | ❌ dropped |

The requirement was "after a confirmed analysis" — this is what makes *confirmed*
mean something checkable rather than something the model asserts. A repro is the
gate because it is the only gate that survives us being wrong about our own reasoning.

### 4.3 A learning is a record, not a paragraph

Prose cannot be deduped, queried, expired, or contradicted. Every entry becomes:

```yaml
---
id: electron-axpress-swallowed
archetype: electron
apps: [Notion, VSCode]
claim: "AXPress returns ok:true on React-routed buttons but produces no state change"
strategy: "compute bounds center, dispatch mouse-click --xy via stealthClick"
status: confirmed
evidence:
  - {run: 2026-08-22T04:00Z, route: notion-library-click,   outcome: fail-then-pass}
  - {run: 2026-08-24T23:27Z, route: notion-screenshot-wa,   outcome: fail-then-pass}
repro: tests/fixtures/notion_axpress_noop/
observed_with: {agent_desktop: "0.4.0", app: "Notion 3.x", os: "macOS 15.x"}
last_validated: 2026-08-29
supersedes: []
---
```

`observed_with` is what makes staleness *detectable*: when `agent-desktop` ships a
fix, everything observed against the old version is flagged for revalidation
automatically instead of silently becoming folklore.

### 4.4 Promotion is batched and mechanical, never per-task

Two rules, both deliberate:

- **The hook writes candidates; only `/ax-learn` promotes.** Mining a transition into
  `candidates/` costs zero model turns and happens on every run. Promotion is a
  judgment call about *generalization*, so it is batched — run weekly, not per-task.
  Per-task promotion means every task ends with the model rationalizing a lesson from
  n=1, which is the failure mode we are trying to escape.
- **The gate is evidence, not eloquence.** `/ax-learn` mechanically refuses to promote
  a candidate whose ledger evidence count is < 2 or which has no repro. The model
  cannot argue its way past the check, because the check runs in `core/ledger.py`
  before the model is consulted.

Batching has a second benefit: seeing ten candidates at once makes duplicates and
near-duplicates obvious, so they get merged instead of accumulated.

### 4.5 It is a cache with eviction, not a log

The part that keeps this from re-becoming the monolith:

- **Hard budget per archetype file** (~40 lines / ~15 rules). A new confirmed learning
  that would exceed the cap must `supersede` or merge into an existing one. Growth is
  forced to be *replacement*, not *accumulation*.
- **Refutation is automatic.** If a confirmed learning's strategy fails verification
  twice, it flips to `refuted` and leaves context without anyone noticing it was
  wrong. This is the self-healing property we do not have today.
- **Nothing is deleted** — demoted entries move to `archive/` with their evidence, so
  we can tell the difference between "never knew this" and "this stopped being true."

Net effect: the knowledge base gets *sharper* over time rather than *longer*, and
context cost stays flat while accuracy climbs.

---

## 5. The app registry: turning known apps into solved territory

§4 makes us smarter about *classes* of application. This makes us smarter about
**this** application. The goal, stated plainly: after a user has worked in Notion for
a month, Notion should no longer be a place we explore. It should be a place we
address.

Every successful run deposits what it learned about that specific app. Every new task
starts by asking the deposit box first.

### 5.1 Two memories — and the distinction must not blur

| | §4 learnings | §5 registry |
|---|---|---|
| Kind | **semantic** — generalizable claims | **episodic** — concrete observations |
| Example | "Electron swallows AXPress on React routes" | "Notion `Library` button sits at `/webarea/nav[1]/button:Library`, reached via Cmd+K" |
| Scope | archetype | one app, one version |
| Size | ~15 rules per archetype, budgeted | unbounded — megabytes |
| Curation | human-gated promotion | fully mechanical |
| **Access** | **loaded into context** | **queried, never loaded** |

That last row is the whole ballgame. The moment we load the registry into context we
have rebuilt the 473k-token Notion tree with extra steps. It is a database. It gets a
query interface, and the model sees only the rows it asked for.

### 5.2 The identity key already exists — we built it in Phase 1

The obvious way to store "where the Library button is" is its `ref_id`. That cannot
work: refs are snapshot-scoped and churn every capture (`:e13` → `:e119` — the same
churn that made our diffs useless).

But `core/axdiff.py` already computes a **stable structural identity** for every node
— role + name + positional path — precisely so the diff could ignore ephemeral refs.
That identity is exactly what the registry needs as a primary key.

> Phase 1 was never only a token optimization. It was the addressing scheme this
> stage depends on. Same key, two consumers.

A registry hit therefore returns a *path*, and the executor resolves that path against
a fresh snapshot to obtain a live ref. Stable across restarts, across sessions, and
across everything except an actual UI change — which is what §5.5 handles.

### 5.3 The cache hierarchy

Every task begins with a lookup, not a snapshot:

| Level | Hit means | Typical cost | Analogy |
|---|---|---|---|
| **L1 — route** | this exact task has been done before | 1 turn, zero discovery | compiled binary |
| **L2 — element** | app is mapped; target and reach-strategy known | 2–3 turns, no full snapshot | symbol table |
| **L3 — archetype** | app unseen, but its class is understood | informed discovery | compiler heuristics |
| **miss** | cold | full exploratory discovery | — |

And every run **promotes downward**: a cold discovery populates L2; an L2 path walked
twice the same way compiles into an L1 route. The system's own usage is what fills it.

This is also the answer to "fewer turns" at its limit. Phase 5 got a route to ≤2 turns
by hand. This gets *arbitrary new tasks on a familiar app* to ≤2 turns without anyone
authoring them.

### 5.4 What a run deposits

```sql
apps(id, bundle_id, name, archetype, version, os_version, last_seen)
elements(id, app_id, identity_path, role, name_pattern, surface,
         reach_strategy,          -- keyboard-macro | axpress | xy | scroll-then-xy
         confidence, hit_count, miss_count, last_confirmed)
routes(id, app_id, task_signature, steps_json,
       run_count, success_count, median_turns, last_success)
outcomes(id, route_id, element_id, ts, verdict, postcondition, turns, tokens)
```

`reach_strategy` is the quietly valuable column. Our learnings already establish that
the right strategy is app-dependent (keyboard macro ≫ physical click ≫ AXPress in
Notion; AXPress-only in OBS). Recording it *per element* means we stop rediscovering
the click paradox on every new button.

`outcomes` is doing double duty: it is simultaneously the registry's confidence
signal and the §4 ledger's evidence stream. One write, two consumers.

### 5.5 Lookup: deterministic first, embeddings only if forced

Recommendation: **SQLite with FTS5**. Zero dependencies, ships with Python, handles
concurrent hook writes, and the corpus is small — hundreds of routes and tens of
thousands of elements, not millions.

Resist reaching for a vector database on day one. Task matching is mostly exact or
near-exact ("send a WhatsApp message to X"), and FTS5 with a normalized task
signature covers it. If fuzzy L1 matching measurably misses, add embeddings *behind
the same `core/recall.py` interface* — that is a swap, not a rewrite.

### 5.6 Staleness and self-repair

Apps update; UI moves. Three mechanisms, all reusing machinery we already have:

- **Verification-linked invalidation.** The Phase 4 hook already tells us when a
  postcondition failed. If the action used a registry entry, that entry is invalidated
  on the spot. *Third* consumer of the same hook.
- **Confidence decay.** `confidence = f(hit_count, miss_count, age)`. Entries below
  threshold are ignored at lookup and rediscovered.
- **Version-stamped bulk invalidation.** App or `agent-desktop` version bump flags the
  profile for revalidation rather than trusting it blindly.

The important property: **a stale hit costs one failed action and then repairs
itself.** A miss triggers rediscovery, which overwrites the entry. The registry heals
through use rather than through maintenance.

### 5.7 Privacy is a design constraint, not a footnote

This database records which apps someone uses and what is in them. Element names are
not neutral — our own learnings contain a real contact name (`Vivek CSE B311`) as an
example. Document titles, message previews, and recipients would all land in
`elements.name` if we were careless.

Design rules, decided now rather than retrofitted:

- **Store selectors, not content.** Stable UI chrome (`"Library"`, `"Send"`) is stored
  verbatim; anything in a content region is stored as a *pattern* plus a salted hash,
  never the literal.
- **Local-only by default.** `registry/` is git-ignored and never leaves the machine.
- **App denylist.** Password managers, banking, Messages — no deposits, ever.
- **Inspectable and erasable.** `/ax-recall --app X` shows exactly what is held;
  deleting a profile directory is a complete forget.

This is also a genuine differentiator: *"it learns your apps without your data leaving
the laptop"* is a sentence worth being able to say.

### 5.8 Why this is the stage that compounds

The first three stages make the agent *better*. This one makes it **cheaper with use**,
which is a different and more durable thing:

- First Notion task: cold discovery, expensive, many turns.
- Tenth: L2 hits, no full snapshots.
- Fiftieth: L1 hit, one turn, near-zero tokens.

Marginal cost per task on a familiar app trends toward zero, and the asset that makes
that true is one no competitor can copy — it is generated by *this user's* usage. A
demo that shows cost-per-task falling across a single session is a far stronger
argument than any static capability claim.

---

## 6. Vision integration: pixels as the failure branch, never the happy path

The last future stage, and the one with the strongest temptation to get wrong.

Screenshot → VLM → response is exactly the loop we built an accessibility-tree agent
to avoid: slow, expensive, and imprecise. But there is a narrow class of failures the
AX tree structurally cannot see, and refusing to look at pixels *ever* means those
failures end in a shrug.

The resolution is a reframe.

### 6.1 Not screenshot-verification — screenshot-*diagnosis*

- **Verification** is a closed question: *did X happen?* The AX tree answers it exactly
  and for free. `saveAsNameTextField.value == "essay.docx"` needs no pixels.
- **Diagnosis** is an open question: *why didn't X happen?* That is inherently visual.

So vision never enters the verification path. It enters the **failure branch** of the
verification path. The happy path stays 100% pixel-free, and the cost is amortized
over failures only — which get rarer as §5 fills.

### 6.2 Ask each sensor what it is actually authoritative for

Most pain here comes from asking a VLM a question the tree answers better, or the
reverse.

| Sensor | Ground truth for |
|---|---|
| **AX tree** | state, value, role, hierarchy, focus, enabled/checked |
| **Pixels** | visibility, occlusion, z-order, rendering, layout, visual fidelity |

The tree has **no z-order truth** — it will report a button at `(x, y)` while a
notification banner is drawn over it. That is not a bug; occlusion is outside what the
tree models. Conversely a VLM will confidently misjudge whether a control is disabled,
which AX knows exactly.

This maps onto our archetypes. The Electron click paradox is precisely the case where
the tree is a *projection* of the DOM that can lag or lie — `AXPress` returns `ok`, the
tree updates, nothing renders. Pixel question. OBS with `bounds: None` is the opposite:
no coordinates at all, but structure fully exposed — AX verification works, a
screenshot adds nothing.

### 6.3 There are free rungs before any model is asked to look

The escalation ladder. Each rung fires only when the one below is inconclusive.

| Rung | Check | Cost | Answers |
|---|---|---|---|
| 0 | AX postcondition | free, deterministic | ~95% of cases |
| 1 | AX re-query after `wait` | free | transient timing |
| 2 | **Region pixel-hash delta** | free, **no model call** | "did *anything* change?" |
| 3 | **Local OCR (Vision.framework)** | free, **no model call** | "is this text present?" |
| 4 | Cropped screenshot → VLM | ~60–200 tok | "is it obstructed?" |
| 5 | Full screenshot → VLM | ~1,500+ tok | last resort |
| 6 | Ask the user | a turn + human time | genuine ambiguity |

Rung 2 is the underrated one: hash the element's region before and after the action
and compare. Zero tokens, no model, and it definitively answers whether the click
landed on *anything* — the most common Electron failure we have documented.

Rung 3 we have already built: `experiments/finder_ocr_click/find_text.swift` is local
macOS Vision OCR. Free, and no model involved.

By rung 4, most cases have already resolved for nothing.

### 6.4 The AX tree is what makes screenshots cheap

The inversion worth noticing: we are not falling back to pixels because the tree
failed — we are using the tree to make the pixel query tiny.

We already hold `bounds` for the disputed element. Crop to it plus padding rather than
sending a full retina frame. Image tokens run roughly `(w × h) / 750`:

| What we send | Tokens |
|---|---:|
| full frame, downscaled to fit | ~1,500 |
| 400×120 crop around the control | **~64** |

~25× cheaper, faster, *and* a more reliable answer, because the model is not hunting a
small control across 3024×1964 pixels. (`agent-desktop screenshot` is window-scoped; if
it gains no region flag we crop locally with `sips`/PIL. What matters is what we send,
not what we grab.)

Keep the question **closed**. Not "what do you see?" but "is the Save button visible
and unobstructed in this crop — yes or no?" One-token answer, nothing to parse.

### 6.5 Trigger on contradiction, not on "stuck"

"Stuck" is a feeling. Contradiction is detectable:

- **AX reports success, the postcondition disagrees** → tree and reality have diverged.
  This is *the* vision case.
- **Same action twice, zero state diff** → input swallowed. Rung 2 catches it free.
- **L1 route replay failed** → UI likely moved; pixels help *rediscovery*, not verification.

Note the first is only detectable *because* Phase 4 exists. Without postconditions we
would be screenshotting on vibes. Another reason vision must come last.

An explicit user request ("show me that it worked") is a separate path with a
different budget — cost is authorized, screenshot freely. Keep the two paths distinct
so the automatic one stays stingy.

### 6.6 Feed the outcome back into §4 and §5

Symmetric with `reach_strategy`: add **`verify_strategy`** to `elements`. If a given
control consistently needs rung 4, store that and skip straight there next time. An app
that never needs rung 2+ keeps free checks forever.

Log *which rung resolved each failure* — that is exactly the §4 evidence shape.
"Elements inside Electron content regions need occlusion checks" is a promotable
learning, and one we could not have guessed.

### 6.7 Where this stays honest

- **A cropped screenshot is not ground truth either.** A VLM will misread a
  disabled-but-visible control. Safe only while we restrict it to the pixel column in
  §6.2. The real failure mode is scope creep: once vision is in the loop, it is
  tempting to ask it everything.
- **Canvas / WebGL / video is a different problem.** Hotstar playback, Figma canvas —
  nothing in the AX tree at all. There pixels are not a fallback, they are the only
  sensor, and no amount of cropping makes that cheap. That is a separate product
  surface, not a gap in this one, and we should say so rather than half-support it.

---

## 7. Migration plan

Ten phases, dependency-ordered. Each has an exit check, so we can stop at any phase
and still have something strictly better than today. Phases 0–5 are the restructure;
6–8 are the compounding stages (§4, §5, §6); 9 is optional upstream work.

### Phase 0 — Scaffold + salvage the corpus
Create the tree above. Copy the consecutive-state JSON pairs out of the old
`experiments/` into `tests/fixtures/` (whatsapp step1→2, step3→4, calendar step2→5,
notion, finder). These stop being scratch dumps and become a **benchmark corpus with
recorded token baselines**.

> **Exit check:** `pytest` runs and prints a token table for every fixture pair.

### Phase 1 — Fix the diff (prerequisite for everything)
Port `state_diff.py` → `core/axdiff.py` with the identity-keying fix: drop `ref_id`,
`bounds`, `available_actions`, `children_count` from the diff key; keep them in a
sidecar `path → {ref_id, bounds}` map the executor resolves against. `context_lines=0`.

Measured on real fixture pairs:

| pair | full snapshot | current impl | identity-keyed | gain |
|---|---:|---:|---:|---:|
| whatsapp step1→2 | 9,936 tok | 6,583 tok | **633 tok** | **10.4×** |
| whatsapp step3→4 | 12,201 tok | 12,004 tok | **2,214 tok** | **5.4×** |

> **Exit check:** test asserts ≥5× reduction vs. the current implementation on every
> fixture. Regression fails the build.

### Phase 2 — Adopt skeleton-first capture
`agent-desktop` already ships `--skeleton` progressive traversal, documented at
78–96% token reduction on dense apps. We currently do the *opposite* —
`--max-depth 40` plus recursive DFS, which is how we produced a 1.9 MB
(≈473k token) Notion tree. Rewrite capture as: skeleton → identify region →
drill down only there.

> **Exit check:** Notion capture-to-target-element drops below 10k tokens.

### Phase 3 — Knowledge → skill
Split `learnings.md` into `references/` by archetype. Dedupe against `AGENTS.md`
(three sections are currently near-verbatim in both files). Add provenance stamps
so we can tell which rules went stale when `agent-desktop` changes.

> **Exit check:** automating Calendar loads zero Electron rules.

### Phase 4 — Hooks
`state_diff_hook.py` (PostToolUse on agent-desktop calls → inject diff) and
`verify_hook.py` (PostToolUse → evaluate declared postcondition, exit 2 on failure).
Tight matchers so they never fire on unrelated Bash.

> **Exit check:** a deliberately broken route is *blocked* by the hook, and the model
> self-corrects without the user intervening.

### Phase 5 — Routes → commands
Port the 11 verified tasks to `commands/routes/*.md`. Replace every `time.sleep()`
with `agent-desktop wait --element --predicate actionable` / `wait --event`.
Replace snapshot-then-parse with `find --role --name`. Batch multi-step
sequences into single `batch` invocations.

> **Exit check:** `vscode-open-folder` completes in ≤2 turns with no fixed sleeps.

### Phase 6 — The learning loop
`core/ledger.py` + `hooks/learn_hook.py` + `commands/ax-learn.md`, per §4. Seed the
ledger by back-filling evidence from the existing `day2/` reports and experiment
READMEs, which already document fail→pass transitions in prose.

> **Exit check:** a candidate with one observation is *refused* promotion; the same
> candidate after a second independent run is promoted, and a confirmed learning whose
> strategy fails twice is auto-demoted out of context.

### Phase 7 — The app registry
`core/registry.py` + `core/recall.py` + `hooks/registry_hook.py`, per §5. Every task
gains a pre-flight recall step before it captures anything. Ship the denylist and the
content-hashing rule in the same phase — not after.

> **Exit check:** run the same Notion task ten times. Turn count and token count must
> fall monotonically and flatten at L1. Then rename a button in the fixture and
> confirm the stale entry self-repairs within one failed action.

### Phase 8 — Vision as the failure branch
`core/vision.py` implementing the §6 ladder: region pixel-hash (rung 2), Vision.framework
OCR (rung 3), bounds-cropped VLM query (rung 4). Wired into the *failure* branch of
`verify_hook.py` only, plus a separate user-invoked path. Adds `verify_strategy` to the
registry.

Depends on Phase 4 — contradiction is undetectable without postconditions.

> **Exit check:** an occluded button (banner drawn over it) is correctly diagnosed, and
> the happy path shows **zero** screenshots taken across a full route replay. Median
> cost of a resolved failure stays under 200 tokens.

### Phase 9 (stretch) — Upstream the MCP crate
`agent-desktop`'s own roadmap has MCP Server Mode as Phase 4, planned but unshipped,
and the design already specifies walking the existing command registry with `rmcp`'s
`#[tool]` macro. That means ~200 lines gets all 58 commands exposed as MCP tools.
Contributing it upstream deletes our subprocess shim and makes the tool loadable by
every MCP client on the market.

---

## 8. What this buys us, against the stated goals

| Goal | Today | After |
|---|---|---|
| **Rich AGENTS.md / learnings** | 253 lines always-on, duplicated across two drifting files, no provenance | thin always-on index + archetype files loaded on demand; single source of truth |
| **Token usage (state_diff)** | diff ≈ full snapshot; 97 of 104 changed lines are `ref_id` churn; log never reaches a model | 5–10× smaller diffs, injected into context automatically by a hook |
| **Fewer turns** | fixed `sleep()`s, 10 full DFS captures where one `wait` would do, discovery re-run every time | `wait`/`find`/`batch`; compiled routes replay in one turn; hooks cost zero turns |
| **Verification** | `in str(tree)` substring check that reports success on failure | typed postconditions in a blocking hook + adversarial verifier subagent |
| **Learning compounds** | append-on-vibes into one monolith; unverified, undated, never evicted | evidence-gated promotion; repro required; auto-refutation; fixed context budget |
| **Known apps get cheap** | every run rediscovers the same UI from scratch | L1/L2/L3 recall; marginal cost per task on a familiar app trends to zero |
| **Failures get diagnosed** | AX-invisible failures (occlusion, render lag) end in a shrug | free pixel-hash/OCR rungs first; ~64-token cropped VLM query as last resort |

Plus three we get for free: it is installable; the domain knowledge is portable to
Codex and Gemini; and `core/` is unit-testable in isolation for the first time.

---

## 9. Honest tradeoffs

We should go in with these acknowledged rather than discover them in week three.

- **Hooks are Claude Code-only.** Codex and Gemini get knowledge + tools but not
  automatic diffing/verification. Mitigated by keeping `core/` importable and
  instructing the Codex path to call it explicitly — but it *is* a worse experience there.
- **We give up programmatic control of the loop.** If we later need headless batch
  runs, benchmarking across hundreds of tasks, or custom routing, the answer is the
  **Claude Agent SDK** — which is Claude Code's harness as a library and still
  consumes the same MCP servers and the same `core/`. The plugin work is not wasted
  in that scenario; it is the same components with a different driver. Worth knowing
  the exit exists before we need it.
- **`agent-desktop` MCP mode does not exist yet.** Bash-to-CLI works today; the MCP
  path is Phase 6, not a dependency.
- **Plugin hook matchers need care.** A loose matcher that fires on every `Bash` call
  would tank performance and pollute context.
- **The learning loop can still be gamed by correlated evidence.** Two runs on the
  same app on the same afternoon are not truly independent — if the real cause was a
  ghost window, we will confirm a wrong lesson twice. The repro requirement is the
  backstop, and `/ax-learn` should weight evidence from *different apps in the same
  archetype* far higher than repeat runs of one route.
- **The registry is a privacy liability if we are lazy about it.** It records app
  usage and UI content. The selector-not-content rule and the denylist are load-bearing,
  not polish, and they must ship in Phase 7 rather than "later."
- **A confidently wrong registry is worse than an empty one.** A stale L1 hit sends the
  agent down a path that no longer exists, and it will look like a regression rather
  than a cache miss. Mitigated by verification-linked invalidation — but it means
  Phase 7 must not ship before Phase 4 is solid.
- **Vision will try to expand its remit.** The moment screenshots exist in the loop,
  every hard question looks like a pixel question, and we drift back into the
  VLM-driven agent we deliberately are not building. The ladder in §6.3 is the control:
  a rung may only fire when the rung below is inconclusive, and that must be enforced
  in `core/vision.py`, not left to judgment.
- **This narrows scope on purpose.** We are betting that "great macOS AX agent inside
  an existing CLI" beats "mediocre general agent we own end to end." That is the
  right bet for the next quarter, and it is reversible via the Agent SDK.

---

## 10. Immediate next steps

1. Scaffold the tree (Phase 0) and salvage fixtures out of the stash.
2. Write `core/axdiff.py` + `tests/test_axdiff.py` with the ≥5× assertion (Phase 1).
3. Rotate the Figma API key that is committed in `LLM_OS/.agents/mcp_config.json`.
4. Review this document, then start Phase 0.
