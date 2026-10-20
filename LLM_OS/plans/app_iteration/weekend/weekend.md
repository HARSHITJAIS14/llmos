# Weekend: Strip openclaw's CUA, drop in agent-desktop

**Thesis.** openclaw is the harness we would otherwise spend months building — agent loop, context compaction, tool registry, permission layers, session storage, channels, subagents. Its *desktop* implementation (Peekaboo / CUA) is vision-first and structurally slow. But the computer-use layer is a **swappable provider slot**. We keep the harness and replace the engine with `agent-desktop`'s semantic AX tree.

Result: openclaw's discipline at agent-desktop's speed, with no vision tax.

---

## 0. Bridge: from `run_claw_task.ts` to a plugin

Today everything is **one script, one process**:

```
npx tsx testing/run_claw_task.ts
  ├── builds a `tools` array from getToolDefinitions()
  ├── while (!done) { POST api.anthropic.com/v1/messages }
  ├── model replies tool_use: "desktop_click_physical"
  ├── switch (toolUse.name) { case ...: }
  └── AxTreeEngine.clickPhysical() → shells to agent-desktop
```

openclaw is not a script — it's a **long-running server plus clients**, because it's built for many agents across many machines and chat channels. Two words:

- **Gateway** — the server. Owns the loop, talks to the model, manages context/sessions/permissions. Your `while` loop, industrialized.
- **Node** — something that can physically *do* things. Connects to the Gateway and announces which commands it can run.

That split lets the brain sit on one machine and the hands on another. For us both are the same Mac; the split is architectural, not physical.

**Where our code lands:**

| today, in `run_claw_task.ts` | after |
|---|---|
| the `while` loop + `fetch` to Anthropic | **Gateway's loop — we delete ours** |
| `tools` array from `getToolDefinitions()` | provider's `capabilities()` — declare supported actions |
| `switch (toolUse.name) { case ... }` | provider's `act()` handler |
| `AxTreeEngine.*` → `agent-desktop` | **unchanged — the engine survives as-is** |
| *(nothing)* | compaction, permissions, sessions, subagents, tri-state verification |

We are not rewriting the engine. We are **deleting our harness** and plugging the engine into a better one.

**What Step 0 was actually asking:** openclaw ships its Mac desktop control inside a separate **Swift application** (`apps/macos/`) with Peekaboo compiled in — an `.app` you'd build in Xcode, sign, and run alongside. If our code had to live in there, we'd be writing Swift and shipping a Mac app. That's the month. It doesn't: providers register from TypeScript, which is why CUA works on Windows and Linux where no Mac app exists. **Answer: no Swift. Same language we already use.**

---

## 1. Why this is a weekend and not a month — verified, not assumed

Four facts, each read from source:

| # | Fact | Evidence |
|---|---|---|
| 1 | `registerComputerUseProvider` is a real, exported plugin-SDK API. Provider is a **5-method interface**: `id`, `label`, `capabilities()`, `isAvailable()`, `openExecution()`. | `src/plugin-sdk/computer-use.ts` |
| 2 | **Returning an `observation` skips the 500 ms sleep AND the full-screen recapture.** | `src/agents/tools/computer-tool.ts:221` |
| 3 | **An observation does not need an image.** Only `kind` is required; `base64`/`format`/`width`/`height` are all `Type.Optional`. `elements[]` carries `elementRef` + `role` + `label` + `value` + `bounds`, capped at 2,000. | `src/plugins/computer-use-contract.ts:333` |
| 4 | The model-facing tool schema is **rebuilt from whatever the provider advertises** — we expose only actions agent-desktop actually performs, and unsupported ones never reach the model. | `computer-tool.ts:92` `replaceParameterSchema(availableActions(...))` |

**openclaw's own doctrine endorses all three of our moves** (root `AGENTS.md`), which means we're working with the framework, not against it:

- *"Latency is model round-trips, not milliseconds. **Collapse act-then-observe pairs into one tool result**."* → exactly the observation play below.
- *"Severity order: **silent failure > crash** > missing feature. Every action ends in a visible outcome or a recorded, intentional non-outcome; an action that silently produces nothing is the worst bug class in this repo."* → the tri-state effect.
- *"Model-context budget: every injected context item is **bounded with a hard cap**; no unbounded items."* → the element cap.

Peekaboo violates the first one (500 ms + a second round-trip after every mutation) and the screen-coordinate path violates the second (returns `ok: true` with no `effect`). We're not deviating from openclaw; we're implementing its stated doctrine better than its default provider does.

Fact 2 + 3 together are the whole play:

```ts
// computer-tool.ts:221
if (actResult.observation || isReadOnlyComputerActAction(action)) {
  // → no sleep, no screenshot
} else {
  await sleep(AFTER_ACTION_SCREENSHOT_DELAY_MS, signal);  // 500 ms
  const capture = await session.captureScreenshot(...);   // full-screen JPEG
}
```

Every mutating action returns a **post-action AX observation**. That kills the 500 ms sleep, kills the JPEG, and *is* the verification step. One round-trip per action instead of two.

---

## 2. Speed math

Measured on this machine (median of 3, `snapshot -i --include-bounds --max-depth 40`):

| | Notion (Electron) | Safari |
|---|---|---|
| `capture_full_dfs_tree` (ours today) | 878 ms · 402 nodes | **5,697 ms** · 280 nodes · **12 still collapsed** |
| single deep call | **221 ms** · 402 nodes | **264 ms** · **485 nodes** · 0 collapsed |

Per-action cost, ours-after vs openclaw-as-shipped (openclaw figures derived from code, not measured — Peekaboo isn't installed here):

| | openclaw / Peekaboo | agent-desktop provider |
|---|---|---|
| semantic click | 2 round-trips + 500 ms + JPEG + base64 + sha256 | **1 subprocess, ~200 ms**, post-state inline |
| observe | full-screen JPEG @1200px | semantic tree, 221–264 ms |
| verification | follow-up screenshot, model must eyeball it | ref resolved + post-condition predicate |

**But the real latency is turns, not perception.** Our own Notion benchmark: 16.19 s total, **9.45 s (58%) in model reasoning across 7 turns**, ~1.35 s/turn. Perception is 4% of the budget. So the wins in priority order:

1. **Cut context per turn.** 402 nodes / 95 KB ≈ **24,000 tokens** per observation today. openclaw caps model-visible elements at 200 (`MODEL_OBSERVATION_MAX_ELEMENTS`). Adopt a hard cap. ~20× reduction.
2. **Cut turns.** Batch actions per round-trip.
3. Perception latency (already cheap; the DFS fix is free money anyway).

---

## 3. Architecture

```
openclaw harness (agent loop · compaction · permissions · sessions · channels)
        │
        │  computer.act  +  screen.snapshot        ← the only two node commands
        ▼
ComputerUseProvider  id: "agent-desktop"
        │
        ├─ observations: ["accessibility"]          ← NOT "image" on the fast path
        └─ agent-desktop (Rust, semantic AX refs)  +  stealth_click (cursor-preserving)
```

**Provider descriptor** — advertise only what we really do:

```ts
{
  contractVersion: 2,
  actions: [ left_click, right_click, double_click, type, key, scroll,
             set_value, invoke_menu, get_window_state, list_windows,
             list_apps, launch_app, bring_to_front, screenshot ],
  targets: ["screen", "window", "element"],
  deliveryModes: ["background", "foreground"],
  observations: ["accessibility"],
  features: { recording: false, agentCursor: false, multiDisplay: true },
}
```

**Action mapping**

| contract action | agent-desktop |
|---|---|
| `left_click` + `elementRef` | `click <ref>` — semantic AXPress, background, no focus steal |
| `left_click` + coords | `--headed mouse-click --xy` via `stealth_click` (returns cursor to user) |
| `type` | `clipboard-set` + `press cmd+v` (our macro trick) or `type <ref> <text>` |
| `set_value` | `set-value <ref> <value>` |
| `key` | `press <combo>` |
| `scroll` | `scroll <ref> --direction --amount` |
| `get_window_state` | `snapshot --app X -i --include-bounds --max-depth 40` → `elements[]` + refs |
| `invoke_menu` | menu-path navigation |
| `screen.snapshot` | `screenshot --app X` + `list-displays` for `displayFrameId` — **tier 3 only** |

**Ref lifecycle maps 1:1 — this is the lucky part.** agent-desktop refs are `@<snapshot_id>:e<N>`; the contract wants opaque `elementRef` + `observationId`. So `observationId = snapshot_id`, `elementRef = qualified ref`. And both systems already agree that a *new* observation supersedes the previous one's refs (openclaw: `superseded-observation-invalidates-elements`; agent-desktop: `update_existing_snapshot` reallocates). Nothing to reconcile.

**The effect tri-state** — steal this outright, it's the highest-value thing openclaw has:

```
ref resolved + --wait-for predicate satisfied  → "confirmed"
ref resolved, no predicate available           → "unverifiable"
ref resolved, post-snapshot byte-identical     → "suspected_noop"
ref did not resolve                            → hard error (STALE_REF / AMBIGUOUS_TARGET)
```

This is the fix for our real accuracy bug. Today `macroType`, `wait`, `setEditorCode`, `expandDfsTree` all return `ok: true` unconditionally, and the Safari DFS reports `complete=True` while leaving 12 nodes unexpanded. An agent that silently believes it succeeded is worse than one that crashes.

---

## 4. Build order

**Step 0 — RESOLVED. No spike needed.**
A plugin-registered provider serves `computer.act` from plain TypeScript with **no native macOS app**. `registerComputerUseProvider` registers both node-host commands itself (`computer-use-contract.ts:637,668`):

```ts
api.registerNodeHostCommand({ command: "screen.snapshot", ... });
api.registerNodeHostCommand({ command: "computer.act",   ... });
```

The entire template is 39 lines — `extensions/cua-computer/index.ts`:

```ts
export default definePluginEntry({
  id: "cua-computer",
  register(api) {
    registerComputerUseProvider(api, createCuaComputerProvider());
    api.registerNodeInvokePolicy(createCuaComputerNodeInvokePolicy());  // required; Gateway fails closed without it
  },
});
```

So the work is: copy that shape, implement the 5-method provider, register a node-invoke policy. Imports come only from `openclaw/plugin-sdk/*`, which satisfies the plugin boundary rule.

**Step 1 — free wins, independent of everything else.**
- Fix `dfs_tree.py`: single deep call first, DFS only for whatever stays collapsed. 4× on Notion, 21× on Safari.
- Correct the "Full DFS Rule" in `.agents/AGENTS.md` and `learnings.md` — as written it mandates the slow path.
- Hard element cap on anything entering context.

**Step 2 — the provider.** Implement the 5 methods, map ~14 actions, return an accessibility `observation` on every mutation.

**Step 3 — the tri-state.** Wire `confirmed`/`unverifiable`/`suspected_noop`, and delete every unconditional `ok: true`.

**Step 4 — prove it.** Same task, N runs, from clean state. Record pass rate + wall-clock + turn count. Replaces the current reports, which hardcode `Status: 🟢 COMPLETED (100% SUCCESS)` into the template regardless of outcome (`run_claw_task.ts:290`) — that's how the Overleaf failure got written up as a success.

---

## 5. Risks

- **Vision gate.** `openclaw-tools.ts:333`: `modelHasVision === false` → the `computer` tool is *not created at all*. Not a real blocker (every Claude 5 model has vision), but it means we can't run a text-only model even though our provider needs no pixels.
- **Eligibility needs both commands.** A node must advertise `computer.act` *and* `screen.snapshot` (`computer-tool-node.ts:62`). This is an *eligibility gate, not a usage requirement* — the tool refuses to talk to a node that doesn't claim both, even if it never calls one. So `screen.snapshot` gets a thin shim over `agent-desktop screenshot` + `list-displays` (for `displayFrameId`), and the model simply never needs it because every action returns an AX observation instead.
- **`registerNodeInvokePolicy` is mandatory.** `computer.act` is a dangerous command; per the contract comment, the Gateway **fails closed** if the policy registration is missing. Not optional.
- **No new config options without approval.** openclaw's `AGENTS.md`: *"Adding any configuration option requires explicit approval in chat before implementation."* Plan the provider to work off existing surfaces; don't invent config keys.
- **Hardcoded machine paths.** `ax-tree-engine.ts:20-21` embeds absolute paths with a username. Must be config/env before this is a real provider.
- **Safety gap to close ourselves.** openclaw's perimeter is strong (six layers, `computer` absent from the default `coding` profile, sandbox+HTTP deny, owner-only, pairing approval, OS TCC). But per its own docs: *"there is no per-action confirmation… no lease, expiry, or arm/disarm."* Once enabled it's hot. For "don't wreck my desktop" we want an arm/disarm and a confirmation gate on destructive verbs. Note `tools.exec.mode` does **nothing** here — it governs host `exec` only.

---

## 6. What we are not doing

- Not rewriting `browser-dom-engine.ts` / `ax-tree-engine.ts`. Both are orphaned (zero importers), untested, absent from `tsconfig`, and `browser-dom-engine.ts` fails `tsc` outright (TS2353 on `coords`). Delete, don't repair.
- Not building vision grounding. Tier 3, later, only if a real app forces it.
- Not touching browsers this weekend. Chromium is already covered by openclaw's `extensions/browser` (52k LOC, CDP + an MV3 extension holding the `debugger` permission → trusted events in the user's live logged-in Chrome/Brave/Edge/Arc). Safari is the genuine gap and is its own project.