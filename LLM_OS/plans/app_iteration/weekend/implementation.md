# Running Real Tasks Through OpenClaw

Runbook for getting a **model-driven** agent to do desktop tasks via our `agent-desktop`
provider. Companion to [`weekend.md`](./weekend.md) (the why).

**Optimization target: turns → tokens → milliseconds.**

---

## 0. What is proven, and what is not

Proven (smoke-tested directly, no Gateway):

- Plugin loads: `status: loaded`, `imported: true`, `activated: true`, zero doctor issues
- `registerComputerUseProvider` registers **both** node commands: `screen.snapshot`, `computer.act`
- openclaw's real contract wrapper validates our payloads (rejected a bad `executionId`)
- `get_window_state` returns live AX refs off the real screen: `[@sfmpqtknc0qx8:e1] webarea "YC — hi"`
- Latency 280–700 ms per action; unsupported actions fail loudly with `ACTION_NOT_SUPPORTED`

**Not proven — nothing below has ever run:**

| piece | state |
|---|---|
| Gateway | never started |
| Node | never paired |
| Agent loop (`packages/agent-core`) | never ran |
| **A model choosing actions** | **never happened — all prior runs were hardcoded scripts** |
| `computer` tool itself | never constructed → the 500 ms-skip, `frameId`, `contextEpoch`, 200-element cap all untested |
| Node-invoke policy / approvals | stubbed as a no-op |

Turn and token counts are **unmeasurable** until a model is in the loop, because turns *are*
model round-trips.

---

## 1. Three hard gates

1. **No embedded mode.** `openclaw-tools.ts:328` — `embedded ? [] : [...createComputerTool()]`.
   `agent --local` and `agent exec` get **no `computer` tool**. A real Gateway + connected node
   is mandatory.
2. **Vision-capable model required**, even though we never take screenshots.
   `openclaw-tools.ts:333` — `modelHasVision === false` → the tool is not created at all.
   Use `anthropic/claude-sonnet-5` (`text+image`, 1000k ctx).
3. **`computer` is not in any default tool profile.** `tool-catalog.ts:400` has `profiles: []`.
   Must be added via `tools.alsoAllow`.

---

## 2. Fix these in the plugin BEFORE running

### 2.1 BLOCKER — the model cannot scope keystrokes to an app

`ComputerActParams` uses `additionalProperties: false`
(`computer-use-contract.ts:88-100`). The `type` and `key` actions accept only
`text`/`keys` + `windowRef`, `elementRef`, `observationId`, `deliveryMode`. **There is no `app`
field.**

So our `appFlag(params)` returns `[]` on every model-issued call, `--app` is never passed, and
keystrokes land on whatever is frontmost. Per `learnings.md` that is the documented cause of
keystrokes leaking into the terminal.

**Fix:** resolve the app from `windowRef` (which *is* in the schema) — cache `list-windows`
output, map `windowRef → app_name`, pass `--app` from that. Fall back to refusing the keystroke
rather than firing it blind.

### 2.2 The verification gate is wrong (this is what broke the Notion run)

The scripted demo typed into Notion's **search box**, producing `cursor for cheit's done bro`,
because the gate asserted a webarea titled "Cursor for CHE" *existed*. It did — behind the modal.
**Presence ≠ focus.**

**Fix:** before any mutation, assert (a) the blocking surface is gone
(`--wait-for-gone`), and (b) the focused element is an editable/text role. Abort otherwise.

### 2.3 The tri-state effect is currently noise

`diffStructuredState` compares only the first **150 of 478** nodes, keyed on
`role:label:bounds`. Observed in one run:

| step | reported | truth |
|---|---|---|
| `cmd+p` | `suspected_noop` | modal **did** open → false negative |
| `return` | `confirmed` | page **did not** open → false positive |

A model told `confirmed` will not retry. **Fix:** diff the full tree, not the capped slice.

### 2.4 Replace sleeps with predicates

agent-desktop has `--wait-for <SELECTOR>`, `--wait-for-gone <SELECTOR>`,
`--wait-timeout <MS>` (default 30000) as global flags. Notion's search needs results to populate
before Enter selects one; a fixed sleep lost that race.

### 2.5 Smaller, still real

- `list_apps` / `list_windows` build `cmdArgs` then discard the result — `observeWindow()`
  overwrites it with a window observation. They do not return app/window lists.
- `diffStructuredState` returns a **boolean**, so the diff-observation token win (§4.2 of the
  old plan) is not implemented. Every action ships the full 150 elements (~4,280 tokens).
- **Token filter not applied.** Observations are 143 elements of mostly `group ""` — unnamed,
  inert layout wrappers. Dropping nodes with no name *and* no action is the single biggest
  token win available and is not done yet.
- `--max-depth 40` is unsafe (`RefMap exceeds 1MB size limit`). Now defaults to 20 with
  degrade to 12→8. Measured: depth 40 FAIL, depth 20 → 1125 nodes/539 ms, depth 12 → 49 nodes/228 ms.
- `invoke_menu` is a stub; it is not in `SUPPORTED_ACTIONS`, so unreachable. Leave it out until built.
- `screenshot` was **removed** from `SUPPORTED_ACTIONS` (your "no screenshots" requirement).
  `screen.snapshot` stays registered because node eligibility demands it, but the model cannot
  invoke it. Combined with advertising `observations: ["accessibility"]` and no coordinate
  actions, the run is pure semantic AX.

---

## 3. Setup runbook

Everything below is a **new** config on this machine (no gateway loaded, no credentials, 235-byte
`openclaw.json`), so nothing of yours gets clobbered.

`pnpm` is **not on PATH** here — use `npx pnpm`. openclaw's internal scripts call `pnpm`
directly and will fail with `spawn pnpm ENOENT`; `npm i -g pnpm` prevents that whole class.

```bash
cd /Users/harshit/Desktop/YC/LLM_OS/openclaw
OC="node scripts/run-node.mjs"
```

### Step 1 — rebuild + refresh after every plugin edit

```bash
git add extensions/agent-desktop/            # discovery is via `git ls-files`; untracked = invisible
npx pnpm build
$OC plugins registry --refresh               # registry is PERSISTED; without this you debug stale cache
$OC plugins inspect agent-desktop --runtime --json | head -20
```

### Step 2 — model auth (vision-capable)

```bash
$OC models auth paste-api-key --provider anthropic      # prompts for the key; use LLM_OS/.env value
$OC models set anthropic/claude-sonnet-5
$OC models status
```

### Step 3 — expose the `computer` tool

```bash
$OC config set tools.alsoAllow '["computer"]'
```

### Step 4 — start the Gateway (foreground, own terminal)

```bash
$OC gateway run
```

### Step 5 — pair this machine as a node (second terminal)

```bash
$OC devices join-code           # mints a single-use onboarding URL
$OC connect <url-from-above>    # foreground node host
$OC nodes list                  # confirm it advertises computer.act + screen.snapshot
```

A node is only routable if it advertises **both** commands (`computer-tool-node.ts:62`).

### Step 6 — run a task, goal-only

```bash
$OC agent --agent default \
  --message "Open the 'cursor for che' page in Notion and type: it's done bro" \
  --json
```

Give it the **goal, not the steps** — otherwise it is a script runner again, the anti-pattern
your own `AGENTS.md` names.

---

## 4. What to measure

From `--json` output, per run:

- **turns** (model round-trips) — the real latency driver; baseline was 7 turns / 16.19 s with
  9.45 s (58%) in model reasoning
- **tokens in/out per turn** — observations are currently ~4,280 tokens each; target ~1,500
- **effect distribution** — `confirmed` / `unverifiable` / `suspected_noop`
- **wall clock** end-to-end — a human does this task in ~6 s

Gate before calling it done: **turns ≤ 4, p50 ≤ 6 s, zero `ok:true`-without-effect,
pass rate ≥ 9/10.**

Do **not** reuse `run_claw_task.ts`-style reporting — it hardcodes
`Status: COMPLETED (100% SUCCESS)` into the template regardless of outcome
(`run_claw_task.ts:290`). That is how a failed Overleaf run got written up as a success.

---

## 5. Expect these mid-run

- Notion ghost windows: multiple windows titled "Notion", `visible: false`, not AX-exposed
  (`ACTION_NOT_SUPPORTED: exists but is not exposed through accessibility`). The model must pick
  the window with a real title via `list_windows`.
- `AMBIGUOUS_TARGET` when a snapshot is unscoped and several windows match — recovery is
  `--window-id`, and agent-desktop says so in its `suggestion` field. Do not flatten that error
  object into a string; it renders as `[object Object]`.
- agent-desktop fails closed on keystrokes it cannot target:
  `ACTION_FAILED: Application has no verified focused element for keyboard delivery`. Good
  behavior — surface it, don't swallow it.
- No `batch` action exists for `computer` (unlike `browser`), and the action enum is closed in
  core. Turn reduction must come from semantic density, not batching.

---

## 6. Verification

**Yours, not ours.** No screenshots are taken by the provider (the `screenshot` action is
unadvertised) and none will be captured for reporting. After a run, check the Notion page
yourself and judge whether it did the task.

One cleanup note: the earlier scripted demo left `cursor for cheit's done bro` in Notion's
search field. Press Escape in Notion to clear it — nothing was written to the document.
