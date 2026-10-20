# atree

macOS desktop automation for Claude Code, built on accessibility trees instead
of screenshots. Wraps the `agent-desktop` CLI with skeleton-first perception,
identity-keyed state diffs (~31–6,000× fewer tokens per look than raw
snapshots), hook-enforced verification, and a per-app memory that makes repeat
tasks cheaper every run.

## Quick start (copy-paste, step by step)

Needs: macOS 12+, Python 3.11+, Claude Code, and a local `agent-desktop`
build (this machine has one at `/Users/harshit/Desktop/YC/agent-desktop`).

**Step 1 — make `agent-desktop` a real command.** Open Terminal and run this
once (already done on this machine):

```bash
ln -sf /Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js /opt/homebrew/bin/agent-desktop
```

After this, `agent-desktop` works as a plain command in every terminal — no
environment variables to remember. (Alternative if you don't use Homebrew:
`export ATREE_AGENT_DESKTOP=/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js`
in `~/.zshrc` — note the `$` when using it: `$ATREE_AGENT_DESKTOP status`.)

**Step 2 — check permissions.** Verify from the terminal you'll actually use:

```bash
agent-desktop status
```

Both `accessibility` and `screen_recording` must say `"granted"`. If either
says `denied`, open the pane and add the app:

```bash
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
```

Click **+**, add **Terminal** (or iTerm), toggle it **on**, then **fully quit
Terminal (Cmd+Q) and reopen it** — the grant is only picked up by a fresh
process.

> **Two gotchas that look like bugs:**
>
> 1. **Permissions belong to the host app, not to you.** macOS grants
>    Accessibility to whatever *launched* agent-desktop. Terminal, iTerm,
>    VS Code, and any Electron-based IDE each need their own grant. Working
>    in one and `denied` in another is expected, not broken.
> 2. **The two permissions are independent.** `screen_recording: granted`
>    with `accessibility: denied` is common — they're separate lists, and
>    granting one never implies the other.

**Step 3 — install the plugin.** Start Claude Code and run two commands:

```bash
claude
```

```
> /plugin marketplace add /Users/harshit/Desktop/YC/atree
> /plugin install atree@atree
```

Restart the session when prompted (`exit`, then `claude` again).

> **After editing plugin files:** bump `version` in
> `.claude-plugin/plugin.json`, then `/plugin marketplace update atree` and
> `/plugin update atree`, then restart. Claude Code runs a **cached copy**
> keyed by version — same version = your changes never load.
>
> **Got `Plugin "atree" not found in any marketplace`?** The marketplace
> catalog is a snapshot taken at add-time and can go stale. Refresh and retry:
>
> ```
> > /plugin marketplace update atree
> > /plugin install atree@atree
> ```

**Step 4 — confirm it's live.**

```
> /plugin list
```

should show `atree@atree · enabled`. Total always-on cost is ~520 tokens; the
hooks are free (no model context).

**Step 5 — first task.** From a new session:

```
> open youtube on safari
```

Watch for `[atree] VERIFIED: …` in the output — that's the verification hook
confirming the result against the live accessibility tree, not the model
guessing.

### Terminal vs VS Code extension

The terminal CLI and the VS Code extension are the same Claude Code sharing
the same user config — a plugin installed from either is available in both.
No re-install needed.

What is **not** shared is macOS permissions: Accessibility and Screen
Recording are granted to the *host app* of the process.

| You run atree from | Needs the grants |
|---|---|
| Terminal.app / iTerm session | Terminal.app / iTerm |
| VS Code extension (or its integrated terminal) | Visual Studio Code |

If `agent-desktop` suddenly fails inside the IDE but works in your terminal,
it's this — grant VS Code both permissions in System Settings → Privacy &
Security, then verify from that same environment:

```bash
agent-desktop status   # both must say "granted"
```

Recommendation: run automation sessions from a real terminal. Tasks activate
and re-focus other apps, and that focus dance interferes less when the
session isn't living inside the editor you're typing in.

## Use it

Just ask for a desktop task in plain language — the `atree` skill triggers on
its own:

```
> open youtube on safari
> send a whatsapp message to Alice saying "running late"
> start an OBS recording
```

Or drive it explicitly with the slash commands:

| Command | What it does |
|---|---|
| `/atree:ax-snapshot Notion` | Skeleton-first inspection of a running app — archetype, windows, interactive regions |
| `/atree:ax-discover mute Slack notifications` | Run the discovery loop for a task the registry doesn't know yet |
| `/atree:ax-recall Safari` | What does atree already know about this app/task? (also the privacy inspection surface) |
| `/atree:ax-learn` | Batched review: promote corroborated learnings into the archetype references |
| `/atree:route-whatsapp-send Alice \| running late` | Compiled route: send a WhatsApp message (recipient-verified) |
| `/atree:route-vscode-open-folder ~/code/myproject` | Compiled route: open a folder workspace in VS Code |

(Type `/atree` and press Tab to see everything the plugin registered.)

What you'll see during a task:

- `[atree] State diff (+13/-2 lines, ~622 tok …)` — perception is diffs, not
  snapshots; the raw tree never enters context.
- `[atree] VERIFIED: …` — every mutating action declared a postcondition and
  a hook checked it against fresh state.
- `[atree] POSTCONDITION FAILED: …` — the action didn't land; the agent is
  blocked from claiming success and follows a diagnosis ladder (scoped
  re-capture → free pixel-hash/OCR checks → one cropped screenshot last).

## Use with Antigravity (or any MCP client)

The same four tools are exposed as an MCP server — this is the atree
"plugin" for hosts that aren't Claude Code (Antigravity, Gemini CLI, Codex,
Cursor, Claude Desktop):

1. **For Antigravity 2.0 (Desktop App):** open the agent panel → **MCP servers** → add a server (it edits the MCP config JSON).
   **For Antigravity CLI (`agy`) or IDE:** Add the following to `~/.gemini/config/mcp_config.json` (global) or `.agents/mcp_config.json` (workspace-specific):

```json
{
  "mcpServers": {
    "atree": {
      "command": "python3",
      "args": ["/Users/harshit/Desktop/YC/atree/mcp/server.py"]
    }
  }
}
```

2. Reload MCP servers (or restart `agy`). The agent gets six tools:
   `ax_recall`, `ax_observe`, `ax_find`, `ax_guide`, `ax_type`, `ax_do` —
   same behavior as Claude Code (ghost windows, Electron drill-down,
   declare+act+verify, clipboard-paste text entry are inside the tools, not
   the host).
3. **The knowledge travels too.** MCP hosts never read skills or markdown
   files, so the archetype references are served *by a tool*: `ax_guide`
   returns the right knowledge file for any app or topic ("Notion" → the
   Electron guide, "dialogs" → save/open sheet patterns, "index" → the
   archetype table), and `ax_recall` tells the agent to call it whenever an
   app is unfamiliar. Edit a reference file and every host sees the new
   knowledge on its next call — no re-install anywhere.
4. Optional but recommended — add one global rule in Antigravity
   (Rules & Workflows) so the habits hold before the first tool call:

   > For any macOS desktop automation: start with atree's ax_recall; call
   > ax_guide for apps you haven't driven this session; enter text only via
   > ax_type (never per-character key presses); act only through ax_do with
   > a postcondition; never use screenshots to find or verify elements.

5. Permissions reminder: the grants belong to the host app — Antigravity
   needs its own Accessibility + Screen Recording (it already has them on
   this machine). If you are using `agy` from a terminal, your terminal app must have these permissions.

What the MCP hosts do NOT get (Claude Code-only): the enforcement hooks and
the learning-candidate mining. `ax_do` still verifies every action — that
logic lives in the tool, not the hook — but nothing blocks an MCP agent that
skips `ax_do` and calls raw commands.

## Try it from a plain terminal (no Claude Code)

The `ax` command (symlinked at `/opt/homebrew/bin/ax`) is the same interface
the model uses:

```bash
ax recall "open youtube" Safari        # what does atree already know?
ax observe Safari                      # digest of interactive elements / diff
ax find Safari "smart search field"    # locate a target with click coords
ax do '{"kind":"title_matches","expect":{"pattern":"YouTube"},"app":"Safari"}' -- press cmd+l
```

Everything in `core/` is host-agnostic Python:

```bash
cd /Users/harshit/Desktop/YC/atree

# what do we know about a task/app?
python3 -m core.recall "open youtube on safari" "Safari"

# app profile / full inspection / erasure (privacy surface)
python3 -m core.registry app Safari
python3 -m core.registry forget Safari

# learning candidates and the promotion gate
python3 -m core.ledger review
python3 -m core.ledger gate safari-windowid-snapshot-not-exposed

# vision ladder on an element's bounds (pixel-hash → OCR → cropped screenshot)
python3 -m core.vision '{"x":100,"y":200,"width":400,"height":120}' 'Save'
```

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest tests/ -q -s     # -s shows the token table
```

The token table in `tests/test_axdiff.py` is the regression gate for the diff
engine — `core/axdiff.py` changes that drop below 5× vs the legacy
implementation fail the build.

```
pair                     full   legacy   axdiff    gain
whatsapp step1->2       9,936    6,583      623   10.6x
whatsapp step3->4      12,201   12,004    2,068    5.8x
```

## Layout

```
core/        host-agnostic engine: axdiff, postconditions, snapshot, ledger,
             registry, recall, vision  (never imports anything host-specific)
skills/      the automation loop + confirmed knowledge, split by app archetype
commands/    slash commands + compiled routes
agents/      ax-verifier — adversarial "prove it landed" subagent
hooks/       Claude Code enforcement: diff injection, postcondition blocking,
             registry deposits, learning-candidate mining
learnings/   unconfirmed candidates + evidence ledger (never loaded, queried)
registry/    per-app SQLite memory (git-ignored, never leaves this machine)
tests/       fixture corpus from real runs + regression suite
```

## Privacy

- The registry stores **selectors, not content**: UI chrome names verbatim,
  anything from a content region as a pattern + salted hash.
- Denylisted apps (Messages, password managers, banking) take no deposits and
  no unsolicited automation.
- `registry/` and `.atree/` are git-ignored and local-only.
  `python3 -m core.registry forget "<App>"` erases an app completely.

## Making it fast

Model choice dominates latency — the plugin's job is cutting tokens and
turns, but each turn's thinking time is the model's.

| Session type | Use |
|---|---|
| Routine desktop tasks, replaying known routes | `/model haiku` — Haiku 4.5 is the latency-class peer of Gemini Flash |
| Same, but you want Opus quality | `/fast` (Opus with faster output) and/or effort → low in `/model` |
| Cold discovery of a tricky app (Electron fights, new routes) | Fable/Opus, high effort — this is where reasoning quality pays |

The atree skill matches ceremony to task (a trivial single action goes
straight to `ax do`/`ax type` — one tool call), and the registry makes repeat
tasks approach one turn regardless of model. A fair speed comparison against
a Flash-class agent is Haiku replaying an L1 route, not a frontier model on
high effort discovering from cold.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Plugin "atree" not found in any marketplace` | `/plugin marketplace update atree`, then install again (stale catalog snapshot) |
| `agent-desktop` errors mention permissions, or hangs | Grant **your terminal app** Accessibility + Screen Recording, then fully quit and reopen the terminal |
| Works in Terminal, fails inside VS Code | Permissions are per host app — grant them to Visual Studio Code too (see below) |
| `AMBIGUOUS_TARGET` / ghost windows | Handled automatically by `core.snapshot.capture`; from raw CLI, pick a `visible: true` window from `list-windows` and pass `--window-id` |
| Window is focused but snapshot says "not exposed through accessibility" | The window is on a freshly-switched Space — use `--surface focused --app "X"` (capture() falls back to this on its own) |
| App times out / `APP_UNRESPONSIVE` | The app is suspended on a non-active full-screen Space — bring it on screen first |

## Design

See [pitch.md](pitch.md) for the full architecture rationale — why a plugin
instead of a standalone harness, the learning promotion gates, the L1/L2/L3
recall hierarchy, and the vision-as-failure-branch rule.
