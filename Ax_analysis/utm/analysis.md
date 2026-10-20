# UTM — Accessibility Tree Analysis

**Bundle:** `com.utmapp.UTM` · **Capture mode:** background (app was not running before capture; window `visible: false`) · **PID:** 25783

## What the app is built with

**Bundle evidence:** the frameworks list is dominated by the QEMU/SPICE backend stack — `qemu-*-softmmu.framework` (one per guest architecture), glib/gobject/gio, GStreamer (`gst*`), pixman, opus, phodav, EGL/GLESv2 — plus `libswift_Concurrency.dylib`. No Electron, Qt, Flutter, or Catalyst hints. The glib/GStreamer stack is the virtualization engine, not the UI toolkit.

**Tree-shape evidence:** the UI is unmistakably **SwiftUI**. The root carries `ax_identifier: "home"` and a child group is identified as `"home, SidebarNavigationSplitView"` — literal SwiftUI view identifiers. Buttons carry SF Symbol names as identifiers (`plus`, `play.circle.fill`), static texts duplicate `name` into `value`, and the layout is the classic SwiftUI wrapper-group nesting around an `outline` sidebar. Verdict: **Swift/SwiftUI front end over a C/QEMU backend**.

## Metrics (full.json, window-scoped)

| Metric | Value |
|---|---|
| Total nodes | 31 |
| Named nodes | 18 (58%) |
| Interactive nodes | 17 (button 12, cell 2, treeitem 2, outline 1) |
| Interactive named | 12 / 17 (71%) |
| Interactive with bounds | 17 / 17 (100%) |
| Truncated containers | 0 |
| Values present | 5 (all statictexts mirror name→value) |
| Nodes with available_actions | 24 |
| Max depth | 8 |
| Roles | dialog 1, group 4, scrollarea 1, outline 1, treeitem 2, cell 2, image 2, statictext 5, button 12, toolbar 1 |

Skeleton capture agrees (compact, `complete: true`, 7 refs); no error envelopes anywhere.

## What the tree exposes

- **The VM library sidebar** as a proper `outline` with `treeitem`/`cell` rows — two VM entries in this capture, each row named with the VM's label plus its machine description, and each carrying an inline, named **Run** button (`play.circle.fill`) with `Click/RightClick/SetFocus`.
- **The empty-state home panel**: five large, fully named buttons — "Create a New Virtual Machine", "Browse UTM Gallery", "User Guide", "Support", "Server" — all with bounds and `Click`/`SetFocus`.
- **Toolbar**: two buttons; one identified as `plus` (new VM) via ax_identifier but neither has an AX name/label.
- **Rich action vocabulary**: `Click`, `RightClick`, `SetFocus`, `SetValue`, `Select`, `Scroll` — full AXPress-style semantic actuation, including right-click for the VM context menus (where most per-VM operations live: edit, clone, delete, share).
- Focused states on rows; every actionable node has pixel bounds.

## What the tree hides

- **5 unnamed interactive nodes**: the two toolbar buttons (one recoverable via the `plus` identifier) and the three 16×16 traffic-light window controls. Minor.
- **The window role is `dialog` and the surface type is `alert`** — SwiftUI's WindowGroup home screen misreports itself; surfaces.json lists exactly one surface titled "UTM" typed `alert`. Don't filter surfaces by `type == "window"` here or you'll find nothing.
- **The big one (not in this capture): the guest display.** Once a VM is running, its window is a SPICE/Metal framebuffer — a rendered bitmap of the guest OS. Nothing inside the guest will ever appear in the AX tree. This capture is the manager window only.

## Quirks

- Background capture of a **non-running app succeeded cleanly** (`was_running: false`, window `visible: false`): the tree is full, bounded, and action-rich — no husk behavior at all. UTM is a model citizen for occluded/background capture.
- Main window reported as `role: dialog` / surface `type: alert` (SwiftUI artifact).
- SwiftUI identifier leakage (`home, SidebarNavigationSplitView`, SF Symbol names) is actually useful as stable native_ids for route compilation.
- VM rows nest treeitem → cell → (image, 2 statictexts, Run button); the row name concatenates label + machine description, so match rows by prefix, not exact string.

## CUA reach strategy

**Semantic AX is the right lane for the manager UI**: select a VM row (`Select` on cell / `Click` on treeitem), start it via the named inline "Run" button, create a VM via the `plus`-identified toolbar button or the "Create a New Virtual Machine" button, and open per-VM menus via `RightClick` on the row. Settings sheets (SwiftUI forms) should expose similarly well.

**Inside a running guest, pure AX is impossible by construction** — the guest screen is pixels. Driving the guest OS requires **vision + coordinate clicks/keystrokes into the framebuffer**, or bypassing the UI entirely (SSH into the guest, or UTM's own scripting/`utmctl` CLI, which is the far better automation surface for VM lifecycle anyway).

## Fidelity score: 9 / 10

+1.5 interactive present & mostly named (5 cosmetic unnamed nodes, one recoverable by identifier) · +2 bounds on 100% of interactive elements · +2 values/states readable (name/value on texts, focused states; no value-bearing controls on this screen to fault) · +2 semantic actions (Click/RightClick/SetValue/Select/Scroll/SetFocus) · +1 stable under background capture, no husk · +1 zero truncated containers → rounded to **9** for the naming gap.

## Verdict

**native-partial, leaning native-perfect for the manager shell.** UTM's SwiftUI front end produces one of the cleanest small trees in the corpus: complete under background capture of a not-even-running app, fully bounded, action-rich, with stable SwiftUI identifiers ripe for compiled routes. The only defects are cosmetic unnamed toolbar/window-control buttons and the dialog/alert role misreporting. The hard boundary is architectural, not AX quality: the guest VM display is an opaque framebuffer, so a CUA agent owns the manager end-to-end via pure AX but must switch to vision/coordinates (or utmctl/SSH) the moment the task crosses into a guest OS.
