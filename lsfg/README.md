# lsfg

A fast macOS desktop agent. Opus 5.5 plans once, the accessibility tree does the work, JEV picks between things on screen when it has to, and every step is checked in code. Tasks that worked once are saved as routes and replay with no model at all.

```
$ lsfg "open youtube on safari"                 (example output)
✓ 0 open_url  Safari https://www.youtube.com          412 ms  [LAUNCH_SERVICES]
done in 0.9 s · 0 model calls · intent:open_site
```

The design is in `implementation.md`. Why each choice was made (and what would change it) is in `reasoning.md`.

## Install

```sh
cd /Users/harshit/Desktop/YC/lsfg
/opt/homebrew/bin/python3.13 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

Put your keys in `~/.lsfg/.env` and lock the file:

```sh
mkdir -p ~/.lsfg
cat >> ~/.lsfg/.env <<'EOF'
TYPESAFE_API_KEY=...      # JEV: choosing between on-screen options
ANTHROPIC_API_KEY=...     # Opus 5.5: planning new tasks
EOF
chmod 600 ~/.lsfg/.env
```

Without `ANTHROPIC_API_KEY`, the built-in intents and learned routes still work. Without `TYPESAFE_API_KEY`, `choose` steps only work when the target's label matches exactly.

**Permissions.** The app you run lsfg from (Terminal, iTerm, VS Code, …) needs **Accessibility** and **Screen Recording** in System Settings > Privacy & Security. Check with:

```sh
.venv/bin/lsfg doctor
```

## Use

```sh
lsfg "open youtube on safari"            # built-in intent, no model
lsfg "search lofi on youtube"            # built-in intent, default browser
lsfg "open notion"                       # opens the app
lsfg "send 'on my way' to Harshita on whatsapp"   # planner; asks before sending
lsfg run --dry-run "..."                 # show the plan, do nothing
lsfg run --yes "..."                     # skip confirmations (careful)
lsfg observe Safari                      # what lsfg sees: the screen digest
lsfg observe Safari --menu               # the app's menu commands and shortcuts
lsfg routes                              # learned routes
lsfg daemon start                        # keep a warm process (faster first calls)
lsfg bench                               # run the bench suite
```

Hold **Esc** or press **Ctrl-C** to stop a running task.

**Siri-style hotkey:** in the Shortcuts app, make a shortcut that runs the shell script `/Users/harshit/Desktop/YC/lsfg/.venv/bin/lsfg --prompt`, and give it a keyboard shortcut.

## What leaves your Mac

- **To Anthropic (planner):** the task, app and window names, a short list of what's on screen (≤ 150 lines), app cards. Only for tasks that need a plan.
- **To TypeSafe (JEV):** the step goal and the labels of the few elements it has to choose between.
- **Never:** screenshots, password fields, or anything from Messages, password managers, and other denylisted apps.

Traces stay in `~/.lsfg/traces/`. `lsfg forget --all` deletes traces, routes, and profiles.

## Tests

```sh
.venv/bin/python -m pytest            # offline: uses the 24-app census in ../Ax_analysis
.venv/bin/python -m pytest -m live    # drives real apps (opt-in)
```
