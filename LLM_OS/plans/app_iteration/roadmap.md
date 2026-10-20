# LLM_OS Application Iteration Roadmap

This folder and document contain the app-by-app iteration plan for LLM_OS. We benchmark, reverse-engineer, and build automated Python tasks for every desktop application installed on this macOS system.

## 1. System App Inventory & Tough Tasks

| Application | Implementation | Tough Task |
|---|---|---|
| AltTab | Native App | Switch to the 5th most recently used window of Chrome |
| Antigravity IDE | Electron | Open a specific file, set a breakpoint on line 42, and start debug mode |
| BetterDisplay | Native App | Change the resolution of the external monitor to 1920x1080 HiDPI |
| BitTorrent | Native App | Add a torrent from URL and set download speed limit to 5MB/s |
| Brave Browser | Web App | Open Youtube.com on private window in brave browser (Done ✅) |
| Canva | Electron | Create a new presentation, add a specific template, and insert an image |
| Claude | Electron | Upload 3 PDFs and ask for a comparative summary |
| Cursor | Electron | Use AI to refactor a specific React component into smaller hooks |
| Discord | Electron | Join a specific voice channel and mute the microphone |
| Docker | Electron | Stop all running containers and prune unused images |
| Firefox | Web App | Open Developer Tools, go to Network tab, and capture HAR file |
| GarageBand | Native App | Create a new project, add a software instrument track, and record 4 bars |
| Gemini | Web App | Start a new chat, switch to Advanced model, and upload an image |
| Google Chrome | Web App | Install a specific extension from the Chrome Web Store |
| HackerRank | Web App | Solve the 'Two Sum' problem in Python and submit the code |
| Keynote | Native App | Add a magic move transition between slide 1 and slide 2 |
| MacDroid | Native App | Mount an Android device in ADB mode and transfer a 1GB file |
| Microsoft Excel | Native App | Create a pivot table from a dataset and add a calculated field |
| Microsoft PowerPoint | Native App | Embed a YouTube video into slide 3 and set it to autoplay |
| Microsoft Teams | Electron | Schedule a meeting for tomorrow at 2 PM and invite 3 specific contacts |
| Microsoft Word | Native App | Generate a table of contents and update all field codes |
| Notion | Electron | Create a linked database and add a formula property |
| OBS | Native App | Set up a new scene with a window capture and a green screen filter |
| Pages | Native App | Export the current document as a PDF with password protection |
| Postman | Electron | Create a new collection, add a POST request, and set up a pre-request script |
| Raycast | Native App | Create a custom script command and assign a hotkey |
| Rectangle | Native App | Snap the current window to the top-left quarter of the screen |
| Safari | Native App | Clear cache and cookies for a specific website |
| SmartBrowser | Web App | Open 10 tabs and cycle through them automatically |
| Telegram | Native App | Create a new channel, add a description, and invite a contact |
| UTM | Native App | Create a new virtual machine using a specific Linux ISO |
| Unstop SmartHire | Web App | Schedule an interview and send invitations to 5 candidates |
| VLC | Native App | Play a video file and add a specific subtitle track with an offset |
| Visual Studio Code | Electron | Open Competitive Programming folder in VS Code and solve A & B of codeforces round 1117 (div2) (Done ✅) |
| WhatsApp | Native App | Send a voice message and a 50MB video file to a specific group |
| Wispr Flow | Native App | Start dictation, speak 3 sentences, and copy the transcription |
| Xcode | Native App | Run the iOS simulator and attach the debugger to a specific app |
| Zoom | Native App | Start a new meeting, enable screen sharing, and record to the cloud |

---

## 2. Desktop Application Iteration Plan

### Phase 1: Core Daily Applications (Current Focus)
- [x] **Calendar** (`Calendar.app`) — *Native AppKit*: Verified event creation, state-diff harness.
- [ ] **Notion** (`Notion.app`) — *Electron*: Page creation, Kanban item editing, Library tab navigation.
- [ ] **WhatsApp** (`WhatsApp.app`) — *Mac Catalyst*: Contact disambiguation prompt, active chat header verification, screenshot dispatch.
- [ ] **Universal Browser DOM Engine** (`utils/universal_browser_dom.py`) — *Web Browser*: Safari, Brave, Chrome, Arc DOM injection bridge.
- [ ] **Calculator** (`Calculator.app`) — *Native AppKit*: Chain arithmetic computation & verification.
- [ ] **Notes & Reminders** (`Notes.app`, `Reminders.app`) — *Native AppKit*: Quick capture, checklist toggling.

### Phase 2: Developer & Communication Tools
- [ ] **Finder** (`Finder.app`) — *Native AppKit*: File search, directory creation, file movement.
- [x] **Visual Studio Code / Antigravity IDE** (`VS Code.app`, `Antigravity IDE.app`) — *Electron*: Workspace folder navigation via native sheet, solution file creation & editor quick open.
- [ ] **Discord / Telegram** (`Discord.app`, `Telegram.app`) — *Electron/Native*: Channel switching, message dispatch.
- [ ] **Postman** (`Postman.app`) — *Electron*: API endpoint execution, environment toggle.
- [ ] **Terminal / iTerm2** — *Native*: CLI command dispatch, process management.

### Phase 3: Media & System Operations
- [x] **System Settings** (`System Settings.app`) — *Native AppKit*: Lock Screen & display sleep timeout configuration, preference extension schemes.
- [ ] **Mail & Messages** (`Mail.app`, `Messages.app`) — *Native AppKit*: Draft email, iMessage dispatch.
- [ ] **Music & TV** (`Music.app`, `TV.app`) — *Native AppKit*: Playlist playback, playback control.
- [ ] **OBS Studio / GarageBand** (`OBS.app`) — *Desktop Native*: Recording toggle, audio monitoring.

---

## 3. App Iteration Lifecycle

For every single application, we execute the 5-stage engineering lifecycle:

$$\text{1. Perception Profiling} \longrightarrow \text{2. Experiment Scripting} \longrightarrow \text{3. State-Diff Harness Log} \longrightarrow \text{4. Safety Verification} \longrightarrow \text{5. Task Promotion}$$

1. **Perception Profiling**: Benchmark tree size, capture latency, and AX node traits.
2. **Experiment Scripting**: Build Python task script in `experiments/<app_task>/`.
3. **State-Diff Logging**: Capture initial state $S_0$, log $(S_0 \xrightarrow{A} S_1)$ unified line diffs to `workflow_execution.diff.log`.
4. **Disambiguation & Verification**: Enforce safety rules (Header match, Title match, Contact selection prompt).
5. **Production Promotion**: Move verified scripts to `tasks/` and update `learnings/learnings.md`.
