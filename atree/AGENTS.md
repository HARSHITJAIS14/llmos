# atree — macOS desktop automation over accessibility trees

Host-agnostic contract. Claude Code loads the full plugin (skills, hooks,
commands); Codex/Gemini users get this file + the `core/` library + the
reference docs, and run the checks the hooks would run automatically.

## What this is

A knowledge-and-verification layer over the [`agent-desktop`](../agent-desktop/)
CLI. The host CLI is the agent loop; this repo contributes:

- `core/` — host-agnostic Python: identity-keyed tree diffs (`axdiff`), typed
  postconditions, skeleton-first capture, evidence ledger, per-app registry,
  vision escalation ladder. Nothing in `core/` imports anything host-specific.
- `skills/atree/references/` — CONFIRMED domain knowledge, split by app
  archetype. Start at `references/archetypes.md`; load exactly one archetype
  file per task.
- `learnings/` + `registry/` — unconfirmed candidates and episodic app memory.
  NEVER loaded into context; queried via `core.ledger` / `core.recall`.

## Non-negotiable rules (any host)

1. **Recall before exploring**: `python3 -m core.recall "<task>" "<App>"`.
2. **Skeleton-first**: never `--max-depth 40`; snapshot `--skeleton`, drill
   only into the region containing the target. Snapshots go to
   `.atree/state/current_snapshot.json`, never into context.
3. **Declare-then-act**: every state-mutating action has a typed
   postcondition (see `core/postconditions.py`). Never verify by substring
   over a serialized tree.
4. **Apps open via `ax open`** (osascript reopen+activate, verified
   frontmost) — never Spotlight, Dock, Launchpad, or UI navigation.
5. **Text entry is clipboard paste** (`ax type` / MCP `ax_type`): atomic,
   registers with Electron/React, restores the user's clipboard. Never type
   character by character; never trust semantic `set-value` in Electron.
6. **No fixed sleeps**: `agent-desktop wait --element/--text/--window/--event`.
7. **Recipient verification**: outbound messages require the chat header to
   match the target BEFORE typing. Mismatch = halt.
8. **Disambiguation**: multiple candidate targets → ask the user; never
   `results[0]`.
9. **Privacy**: denylisted apps (Messages, password managers, banking) take
   no deposits and no unsolicited automation. `registry/` never leaves the
   machine.

## Supersessions of the original ATree_tool rules

This repo descends from `LLM_OS/ATree_tool`. Most learnings carried over
verbatim (see `skills/atree/references/`). Three original rules were
DELIBERATELY inverted — if you compare the repos, these are design changes,
not drift:

| Original rule (ATree_tool) | Now | Why |
|---|---|---|
| "Use `--max-depth 40` to get deep trees in a single call" / "Full DFS tree at every step" | Never. Skeleton-first, drill only into the target region | Full DFS produced a 1.9 MB (~473k-token) Notion tree; skeleton+drill reaches the same element for ~1k tokens |
| "Never summarize JSON snapshots — save pretty-printed to disk for the user to inspect" | Raw trees never reach context; the model sees a digest or an identity-keyed diff | The original rule served human debugging; feeding raw trees to a model is the main token sink this repo exists to eliminate |
| Per-task Python scripts in `tasks/` with pre-baked sleeps | Compiled route commands + `ax do` postconditions; `wait` predicates, zero fixed sleeps | Sleeps were the old harness's own anti-pattern rule that its tasks violated |

Carried over unchanged and load-bearing: keyboard-macro-first for Electron,
the stealth-click pointer-restore binary (`scripts/stealth_click`, used by
`ax do` for every physical click), the AXPress semantic exception,
keystroke-leakage activation rules, recipient verification, disambiguation,
ghost-window filtering, offscreen scroll-to, Space suspension, all
app-specific quirks, dialog/RTF/deep-link patterns.

## Layout

`core/` library · `skills/` confirmed knowledge + promotion rules ·
`commands/` slash commands + compiled routes · `hooks/` Claude Code
enforcement · `learnings/` candidates/ledger/archive · `registry/` SQLite
(git-ignored) · `tests/` fixture corpus + regression suite (`pytest`).

Requires: macOS 12+, `agent-desktop` on PATH (or `ATREE_AGENT_DESKTOP` env),
Accessibility + Screen Recording permissions, Python 3.11+.
