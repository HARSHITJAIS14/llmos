# testing_out — reference clone of `fazm`, mined for CUA features

This directory holds a **stripped, read-only reference copy** of
[mediar-ai/fazm](https://github.com/mediar-ai/fazm) (`fazm/`, at commit
`ecaeb57e`, "Release changelog for v2.9.87").

It is kept for **source reading only**. All build output, vendored binaries, and
media assets have been deleted — this tree **cannot be built or run**. See
[Deleted inventory](#deleted-inventory) for what was removed and how to restore it.

Purpose: fazm is the closest shipped product to the CUA we are building
(`../agent-desktop`, `../atree`), so this is the map of what to port.

---

## What fazm actually is — read this first

**fazm is not an accessibility-tree CUA.** Its entire perception/action layer is
Claude Code + Playwright + screenshots. Only three files in the whole app touch
`AXUIElement` / `CGWindowList`:

- `fazm/Desktop/Sources/AppState.swift`
- `fazm/Desktop/Sources/MainWindow/ClickThroughView.swift`
- `fazm/Desktop/Sources/FloatingControlBar/ScreenCaptureManager.swift`

So **there is nothing here to copy for the core observe/act loop.** Our
`agent-desktop/crates/macos/src/tree` + atree's identity-keyed diffing is well
ahead of it.

What fazm *does* have, and we don't, is **the entire product shell around a
CUA**: permissions onboarding, voice, scheduling, approval gating, a proactive
screen observer, telemetry, auto-update, and signed distribution. That is where
all the value in this tree is.

### Architecture in one paragraph

A SwiftUI menu-bar app (`Desktop/`) renders a floating control bar and spawns a
Node **ACP bridge** (`acp-bridge/`) as a subprocess. The bridge speaks
[Agent Client Protocol](https://github.com/agentclientprotocol) to a swappable
backend — Claude Code, Codex, or Gemini CLI — and exposes app capabilities back
to the agent as an MCP stdio server (`fazm-tools-stdio.ts`). Browser work goes
through Playwright MCP (user's real Chrome) or a bundled managed Chrome driven
over CDP. State lives in a per-user SQLite DB via GRDB. A Rust backend
(`Backend/`) brokers model keys, Stripe, and GCS uploads.

```
Desktop/          Swift/SwiftUI macOS app (SPM package) — UI, permissions, voice, DB
acp-bridge/       Node/TS — ACP bridge to Claude/Codex/Gemini + MCP tool server
Backend/          Rust (axum) — key brokerage, Stripe, appcast, GCS signed URLs
web/              Next.js marketing/app site
inbox/            launchd-driven autonomous agent pipelines (dev-machine ops)
Installer/        Swift helper for the DMG installer
scripts/          release, appcast, GCS, session-recording tooling
```

---

## Port list

Tiered by how much work it is to reuse. Line counts are from this snapshot.

### Tier 1 — drop-in (zero or trivial dependencies)

| What | File | Notes |
|---|---|---|
| **Approval gate ("cage mode")** | [`fazm/acp-bridge/src/approval-gate.ts`](fazm/acp-bridge/src/approval-gate.ts) — 225 lines, **zero imports** | `off` / `destructive` / `always`. Gates ACP `session/request_permission` by tool `kind` (`edit`/`delete`/`move`/`execute`), with a 300s timeout flush so a pending gate can never hang a session forever. **This is the biggest safety gap in `ax do` right now.** Pure logic — ports to Python/Rust in about an hour. |
| **Schedule parser** | [`fazm/acp-bridge/src/schedule.mjs`](fazm/acp-bridge/src/schedule.mjs) — 114 lines, **zero imports** | `cron:0 9 * * 1-5` / `every:1800` / `at:<iso8601>` → `computeNextRun()`. Self-contained 5-field cron implementation. |
| **Recurring-task system** | [`CronJobStore.swift`](fazm/Desktop/Sources/CronJobStore.swift) (298) + [`RoutineScheduler.swift`](fazm/Desktop/Sources/Chat/RoutineScheduler.swift) (177) + [`cron-runner.mjs`](fazm/acp-bridge/src/cron-runner.mjs) (397) | `cron_jobs`/`cron_runs` schema, 60s tick, **catch-up-once** semantics (a missed `next_run_at` stays in the past and fires once on next launch), and a `/tmp/fazm-routine-<id>.pid` single-flight lock so two schedulers never double-fire the same job. Agent-facing tools at `fazm-tools-stdio.ts:548-604`. |
| **Screenshot budget tricks** | [`ScreenCaptureManager.swift`](fazm/Desktop/Sources/FloatingControlBar/ScreenCaptureManager.swift) (196) | We already have `crates/macos/src/system/screenshot.rs`, but two bits are worth porting: (1) downscale to 1568px longest edge + JPEG quality ladder 0.7→0.3 until under 3.5 MB, so base64 never blows the vision API limit; (2) if window *metadata* is readable but `CGWindowListCreateImage` returns nil, report **stale Screen Recording grant** rather than "no window found". Also `cleanupOldScreenshots(olderThan:)`. |
| **Dev/prod data-root split** | [`Extensions/AppPaths.swift`](fazm/Desktop/Sources/Extensions/AppPaths.swift) | Bundle-ID-keyed support root, so a dev build's data migrations can never touch prod user dirs. Unknown bundle ID falls back safely. |
| **Single-instance lock** | [`InstanceLock.swift`](fazm/Desktop/Sources/InstanceLock.swift) (177) | Foundation + AppKit only. |
| **Global hotkey registration** | [`FloatingControlBar/GlobalShortcutManager.swift`](fazm/Desktop/Sources/FloatingControlBar/GlobalShortcutManager.swift) (173) | Carbon `HIToolbox` only. |
| **Language → TTS voice routing** | [`VoiceLanguageRouter.swift`](fazm/Desktop/Sources/VoiceLanguageRouter.swift) (158) | `NaturalLanguage` only. |
| **"Agent is driving" overlay** | [`fazm/acp-bridge/browser-overlay-init.js`](fazm/acp-bridge/browser-overlay-init.js) (128) | Injected glow + status pill. Registered via `addInitScript` so it survives navigation ([`browser-overlay-init-page.ts`](fazm/acp-bridge/browser-overlay-init-page.ts)). Generic affordance for telling a user a CUA has the wheel. |

### Tier 2 — copy the architecture, not the file

**Proactive observer loop — the single most valuable thing in this repo.**
[`SessionRecordingManager.swift`](fazm/Desktop/Sources/SessionRecordingManager.swift) (632) records the *active window* at 5 FPS into H.265 chunks;
[`GeminiAnalysisService.swift`](fazm/Desktop/Sources/GeminiAnalysisService.swift) (1299) buffers ~60 minutes (buffer persisted to disk, survives app restarts), then makes one multimodal call with tool access (`query_database`, `read_dev_log`, `get_active_sessions`) returning `VERDICT: NO_TASK | TASK_FOUND | UNCLEAR`.

Steal the **prompt** at `GeminiAnalysisService.swift:12-71` more or less verbatim. It encodes hard-won anti-false-positive rules:
- mandatory dedupe query against the `observer_activity` table before suggesting anything;
- "check whether the agent is *already* doing this work" — they call this the most common false positive;
- prefer `UNCLEAR` over guessing ("a wrong suggestion is worse than no suggestion");
- explicit AI-is-faster-at / AI-is-slower-at lists;
- an `automate` vs `heal` split, where `heal` covers visible Mac health symptoms and is constrained to read-only diagnostics first.

For a model we are training, this loop doubles as a **training-data harvester**.
Note also `SessionRecordingManager.cleanupStaleRecordings()` — the two documented
ways recording chunks silently accumulate forever, and the age-based sweep that
fixes it.

**Programmatic control surface** — documented at `fazm/CLAUDE.md:132-169`.
A `com.fazm.control` distributed notification with ~20 commands (`getState`,
`newChat`, `setModel:`, `sendFollowUp:`, `setWorkspace:`, `setBrowserMode:`,
`restartBridge`, …), where `getState` dumps full UI state as JSON to a
bundle-scoped `/tmp/fazm-control-state-<scope>.json`. **This is effectively an
eval harness for a GUI agent** — it lets you benchmark the app without having to
automate your own UI. Also note the `restartBridge` SIGHUP pattern: it defers
process exit until the in-flight turn completes, so a pending `tool_use_id`
always receives a `tool_result` (an immediate SIGTERM here used to brick any
session that invoked it).

**Agent requests its own permissions** — `check_permission_status` and
`request_permission` are exposed to the agent as tools
(`fazm-tools-stdio.ts:360-383`), backed by the GIF-driven onboarding flow
([`SessionRecordingPermissionWindow.swift`](fazm/Desktop/Sources/SessionRecordingPermissionWindow.swift) 261,
[`AppManagementSetup.swift`](fazm/Desktop/Sources/AppManagementSetup.swift) 318,
[`BrowserExtensionSetup.swift`](fazm/Desktop/Sources/BrowserExtensionSetup.swift) 870,
[`MainWindow/Pages/PermissionsPage.swift`](fazm/Desktop/Sources/MainWindow/Pages/PermissionsPage.swift)).
The idea worth taking: mid-task permission recovery instead of hard failure.

**Multi-provider ACP runtime** — [`index.ts`](fazm/acp-bridge/src/index.ts) (7145) +
[`protocol.ts`](fazm/acp-bridge/src/protocol.ts) (797) + `codex-provider.ts` / `gemini-provider.ts` +
[`oauth-flow.ts`](fazm/acp-bridge/src/oauth-flow.ts) (457) and `codex-oauth-flow.ts` (405).
If we ever ship a standalone app rather than a Claude Code skill, this is a
swappable-backend harness with OAuth, an `auth_required` event, and API-failure
handling already solved.

**Voice stack** — [`PushToTalkManager.swift`](fazm/Desktop/Sources/FloatingControlBar/PushToTalkManager.swift) (879) +
[`AudioCaptureService.swift`](fazm/Desktop/Sources/AudioCaptureService.swift) (933) +
[`TranscriptionService.swift`](fazm/Desktop/Sources/TranscriptionService.swift) (741) +
`AudioDeviceManager.swift`, plus silence-overlay windows. Originally ran against
a bundled `silero_vad.onnx` (deleted here — see inventory).

**Skills install & versioning** — [`SkillInstaller.swift`](fazm/Desktop/Sources/SkillInstaller.swift) (319)
auto-discovers `Sources/BundledSkills/*.skill.md` and reinstalls to
`~/.claude/skills/` on checksum change, no code edit needed to add a skill.
[`skills-lock.json`](fazm/skills-lock.json) pins `source` + `sourceType` +
`computedHash` per third-party skill. atree ships skills already; this is the
supply-chain and update story we don't have.

**Long-running-agent watchdog** — [`ResourceMonitor.swift`](fazm/Desktop/Sources/ResourceMonitor.swift) (1615) +
[`ResourceCounters.swift`](fazm/Desktop/Sources/ResourceCounters.swift) (57). FD / window / leak
tracking for a process expected to stay up for days.

**Local context layer** — [`FileIndexing/`](fazm/Desktop/Sources/FileIndexing/):
`FileIndexerService.swift` (398), `KnowledgeGraphStorage.swift` (127),
`AIUserProfileService.swift`. File index + knowledge graph fed to the agent as
context, with `scan_files` / `save_knowledge_graph` as agent tools.

### Tier 3 — ops scaffolding (pure time savings)

- [`fazm/inbox/`](fazm/inbox/) — launchd-driven autonomous agent pipelines
  (`launchd/*.plist` + `skill/*.sh`) with `lock.sh` single-flight and per-run log
  files. Four services on 15s–20min intervals.
- [`fazm/reset-and-run.sh`](fazm/reset-and-run.sh) — clean-slate reset of
  onboarding, permissions, and UserDefaults. Directly useful for reproducible
  CUA testing.
- [`fazm/codemagic.yaml`](fazm/codemagic.yaml) (92K), `build.sh`,
  `build-local-prod.sh`, [`verify-release.sh`](fazm/verify-release.sh),
  `distribute.sh`, `scripts/prepare-release.sh`, `scripts/generate-appcast.sh`,
  `scripts/deploy-appcast.sh` — signed + notarized DMG and Sparkle appcast.
- [`UpdaterViewModel.swift`](fazm/Desktop/Sources/UpdaterViewModel.swift) (545) +
  [`UpdateRollbackManager.swift`](fazm/Desktop/Sources/UpdateRollbackManager.swift) (317) —
  Sparkle auto-update **with rollback**.
- Telemetry: `AnalyticsManager.swift`, `PostHogManager.swift`, Sentry wiring, and
  the `.claude/skills/` release skills. PostHog feature flags gate session
  recording.
- `fazm/CLAUDE.md` / `AGENTS.md` (identical, 23K) — the debugging runbook:
  debug-trigger notification names, SQL queries for diagnosing routines, active-user
  lookup via `defaults read com.fazm.app auth_tokenUserId`. Worth reading in full.

### Skip

- `fazm/Backend/` + `fazm/web/` — Firebase/Firestore/GCS/Stripe/paywall/referral.
  Only relevant if we copy their hosted-key business model.
- `fazm/Desktop/LocalPackages/Highlightr` — syntax highlighting. Irrelevant.
- `fazm/Desktop/Sources/DeletedTypeStubs.swift` (52K) — dead-code graveyard.
- The perception/action core, as covered above.

---

## Deleted inventory

Removed to get the working tree from **6.6 GB → 8.0 MB** of source and docs.
Nothing removed is fazm source; all of it is regenerated by a build or
re-downloaded.

`fazm/.git` (80.6 MB) is **intentionally retained**, so the directory is 89 MB
on disk. Keeping it means deleted assets below are recoverable locally with
`git checkout -- <path>`, and the provenance needed for the licensing question
stays available.

| Path | Size | Restore with |
|---|---|---|
| `fazm/Desktop/.build/` | 5.2 G | `swift build` (SPM cache) |
| `fazm/build/Fazm Dev.app` | 766 M | `./run.sh` |
| `fazm/acp-bridge/node_modules/` | 462 M | `npm ci` (lockfile kept) |
| `fazm/acp-bridge/dist/` | 672 K | `npm run build` |
| `Resources/ffmpeg` | 63 M | upstream binary — **note: likely GPL/LGPL** |
| `Resources/cloudflared` | 37 M | upstream binary |
| `Resources/installing_extension.gif` | 16 M | git history / upstream |
| `Resources/permissions.gif` | 6.7 M | git history / upstream |
| `Resources/enable_notifications.gif` | 6.3 M | git history / upstream |
| `Resources/enabling_token.gif` | 6.1 M | git history / upstream |
| `Resources/accessibility_permission.gif` | 5.0 M | git history / upstream |
| `Resources/silero_vad.onnx` | 2.1 M | public Silero VAD model |
| `LocalPackages/Highlightr/src/assets/styles/` | 2.0 M | vendored highlight.js CSS themes |

Kept: all Swift, TypeScript, Rust, Python, and shell source; all Markdown docs;
`CHANGELOG.json`; all build/release scripts and CI config; app icons and small
UI assets; `Highlightr`'s Swift classes.

---

## Licensing caveat — resolve before copying any code

`fazm/README.md` states MIT and "fully open source", but **there is no `LICENSE`
file anywhere in this clone** (checked the repo root and one level down). The git
remote is `https://github.com/mediar-ai/fazm.git`.

Our `agent-desktop` is **Apache-2.0**. Before merging any of the above:

1. Confirm the actual license on GitHub upstream.
2. Preserve attribution headers on anything copied more than trivially.
3. Note that bundled third-party binaries carry their own terms. `ffmpeg` in
   particular is likely GPL/LGPL, which is a genuine problem for a signed,
   distributed app; `cloudflared` and `silero_vad.onnx` need checking too.

---

## Suggested first port

`approval-gate.ts` → Python, wired into `atree`'s `ax do`. It is 225 lines with
zero dependencies, it closes the largest safety gap in our action path, and it
needs no other part of fazm to be useful.
