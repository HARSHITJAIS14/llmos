# AX playbook: 7 procedures with no model in the loop

Built only from the 59 laws in `laws.md` / `mined_laws.json` plus the 12 lifecycle laws in `lifecycle_laws.json`.
Tool: agent-desktop 0.8.1. Corpus: 24 apps. Nothing here is a new law. Where a step has no law behind it, it says **UNTESTED**.

Law ids: `LAW-WIN-n`, `LAW-ACT-n`, `LAW-ID-n`, `LAW-TXT-n`, `LAW-STR-n` (from `laws.md`), and `LAW-LIFE-1..12` (lifecycle, in file order):

| id | short name |
|---|---|
| LIFE-1 | husk = depth cap; deeper recapture is a strict superset |
| LIFE-2 | untrusted predicate: frontier OR n <= 12 (10/10, 0 FP) |
| LIFE-3 | 7-node skeleton, 4 root kids = Chromium shell (6/6, 0/16) |
| LIFE-4 | native trees are fine in the background; never activate to read |
| LIFE-5 | root offscreen = hidden window, content still trusted |
| LIFE-6 | bounds and root role belong to one snapshot |
| LIFE-7 | complete=false is a stable prefix; don't drill (0/7) |
| LIFE-8 | Telegram-style opaque root: give up on first capture |
| LIFE-9 | RefMap > 1MB: split by frontier refs |
| LIFE-10 | window_without_accessibility_element / AMBIGUOUS_TARGET = wrong target |
| LIFE-11 | launch transient: stable window id + n > 12 |
| LIFE-12 | readiness ladder (24/24 captures routed) |

---

## 0. Shared helpers

```
walk(node)             pre-order, yields (node, depth, ancestors)
n                      number of nodes in data.tree
maxd                   max serialized depth
frontier(t)            nodes with (children_count or 0) > len(children)
norm(s)                strip U+200E/200F/202A-E/2066-9/200B-D/2060/FEFF/00AD -> NFC -> strip()     # LAW-ID-10
area0(x)               x.bounds.width <= 0 or x.bounds.height <= 0                                 # LAW-ID-7
has_value(x)           'value' in x  (key present; missing key = empty)                            # LAW-TXT-1
webarea(t)             shallowest node with role == 'webarea', or None
snap(win, depth)       agent-desktop snapshot --window-id <win.id> --max-depth <depth> -i           # never --app  (LAW-LIFE-10)
```

Global rules every procedure obeys:

```
G1  never store a ref_id; a ref '@S:eN' is valid only while S == current snapshot_id     # LAW-ID-8
G2  after any action, activate, open -a, or Space switch: drop cached bounds, re-snapshot # LAW-LIFE-6, LAW-ID-8
G3  root role 'window' == 'dialog'; never gate on it                                      # LAW-LIFE-6
G4  assert data.app == intended app before using a capture                                # LAW-STR-12
G5  complete=true does NOT rule out depth capping                                         # LAW-STR-6
```

---

## 1. READY: get a trustworthy tree

**Input:** app name, pid, a window from PICK-WINDOW, `FW` from CLASSIFY if known.
**Output:** `(tree, status)` with status in `TRUST | TRUST_PREFIX | TRUST_READ_ONLY | NON_AX`, plus `hidden` flag.
**Laws:** LIFE-1,2,3,4,5,7,8,9,11,12; STR-3,6,7,8,9.

```
R0  depth = 10
    sk = snapshot --skeleton (cheap)
    if sk.n == 7 and len(sk.root.children) == 4: depth = 40            # Chromium shell  LIFE-3
    t = snap(win, depth)

RE  on error:
      ACTION_NOT_SUPPORTED kind window_without_accessibility_element -> PICK-WINDOW again; if same -> activate,
                                                   snapshot --surface focused --app; go R2          # LIFE-10
      AMBIGUOUS_TARGET  -> pick the pid that owns win; re-snap by --window-id                        # LIFE-10
      INTERNAL and 'RefMap' in message -> SPLIT (below)                                              # LIFE-9
      APP_UNRESPONSIVE and loaded_count == 0 and count_changed == false -> return NON_AX             # LIFE-8

R2  if n == 1 and root.subtree_truncated and ref_count == 0: return NON_AX                           # LIFE-8, STR-8
R3  if n <= 12:
       re-list windows; activate; wait 2s; t = snap(win', depth)   (once)                            # LIFE-11
       if still n <= 12: return NON_AX
R4  if frontier(t) or maxd == depth:                                                                 # LIFE-1, LIFE-2, STR-6
       if depth < 40: t = snap(win, 40); goto R2        # no activation, no waiting
       else: drill each frontier ref:  snapshot --root <ref> --snapshot <sid> --max-depth 40
R5  if complete == false and nodes_observed > n: status = TRUST_PREFIX                                # LIFE-7, STR-7
       deepest subtree_truncated node = boundary                                                     # STR-8
       boundary has 0 children and no drill_result -> mark that subtree OPAQUE                        # STR-9
       boundary is list/outline with > 100 same-shape kids -> sample first 20, treat rest as rows     # STR-9
       NEVER drill, retry or activate here (0/7 drills worked, up to 45s each)                        # LIFE-7
R6  hidden = 'offscreen' in root.states or (offscreen/n >= 0.9 and complete == true)                  # LIFE-5
       if hidden: status = TRUST_READ_ONLY    (names/values fine; ACTIVATE + re-snap before acting)
R7  else status = TRUST
    native tree (no webarea, complete, maxd < depth, n > 12): trust it from the background            # LIFE-4, STR-3

SPLIT (RefMap overflow):
    t10 = snap(win, 10); for ref in frontier(t10): snapshot --root ref --max-depth 40, merge
    if a drill still overflows: step depth 10 -> 20 -> 30, keep the largest that works               # LIFE-9 (remedy UNTESTED)
    never retry the same scope; never drop -i
```

**On failure:** `NON_AX` goes to ESCALATE. A capture that hits R4 at depth 40 and still has frontier after drilling also goes to ESCALATE (trigger E3).
**Replay:** routes all 24 default captures: TRUST 8, R4 8 (7 reach TRUST at depth 40, Antigravity goes to SPLIT), R5 4, R6 3, R3 1 (Keynote -> 689-node prefix), R2 1 (Telegram). No foreground capture wrongly fired R2/R3/R4/R6 (LIFE-12).
**Do not use as husk signals:** offscreen counts, name counts, `complete=false` (adds 2 FPs: Finder, Reminders) (LIFE-2).

---

## 2. PICK-WINDOW

**Input:** `list-windows` output for the app, app name.
**Output:** `win` (window id + title) and `bounds_source` in `WS | AX_ROOT`.
**Laws:** WIN-1..10, LIFE-5, LIFE-6, LIFE-10, LIFE-11, STR-12.

```
P1  drop ghosts:                                                                           # WIN-1, WIN-2, WIN-9
      ghost(w) := not w.visible and not w.is_focused and w.title == w.app_name
                  and ((w.h <= 30 and w.w >= 1000) or (w.w,w.h) in {(0,0),(1,1),(64,64),(500,500)})
    any w with title != app_name is never a ghost                                          # WIN-7
P2  if a window is focused: return it, bounds_source = WS (exact to 0px, 6/6)              # WIN-3
P3  thumb(w) := w.w <= 200 and w.h <= 200            # Dock proxy; title is real, bounds lie 34x-126x   WIN-4
    nonthumb = [w for w in kept if not thumb(w)]
    pick = max(visible nonthumb, by area) or max(nonthumb, by area)                        # WIN-6
P4  if no pick: pick = thumb with the real title (title witness only), bounds_source = AX_ROOT
    if nothing survives at all: do NOT say "no window"; snapshot and use AX root bounds    # WIN-10 (Finder 9/9 ghosts)
P5  after first snapshot: if pick.bounds != ax_root.bounds exactly -> bounds_source = AX_ROOT
                                                  (window minimized / other Space)         # WIN-5
P6  just launched? list twice ~2s apart; continue only if pick.id is the same both times   # LIFE-11
P7  never reject a window for negative x or x > 2560; displays come from menu-bar strips   # WIN-8
P8  assert snapshot data.app == app and window id is the one picked                        # STR-12
```

**On failure:** `window_without_accessibility_element` -> redo P1-P5 with fresh `list-windows`; if the same, activate and use `--surface focused`. `AMBIGUOUS_TARGET` (Firefox: 11 same-name processes) -> choose the pid that owns `pick`, always address by `--window-id` (LIFE-10).
**Measured:** ghost filter flags 130/161 windows with 0 FP; best-window 15/15 on winnable apps, the other 9 are the detectable thumbnail/absent class (WIN-1, WIN-6).

---

## 3. FIND: "the X in app Y" -> element

**Input:** a selector `sel = {native_id?{kind,value}, role, name, value?, nth?, path?}` built earlier, or a plain `(role-concept, text)` query; a READY tree; `FW`.
**Output:** one node + its `ref_id` from the current snapshot, or `NOT_FOUND | AMBIGUOUS`.
**Laws:** ID-1..12, ACT-1, ACT-5, ACT-6, ACT-8, ACT-12, TXT-4, TXT-5, TXT-9, TXT-11, STR-2, STR-10, STR-11.

```
F0  scope:
      FW == chromium-family (Electron): search only under webarea + depth-1 window buttons      # STR-2
      FW == chromium browser / gecko: webarea + shell (browser chrome lives in the shell)       # STR-2
      role 'browser' at depth ~3 under unnamed groups -> it is a file panel, use Finder rules   # STR-11
F1  drop area0 nodes from all candidate lists (22 of 26 residual clones)                        # ID-7
F2  map concepts to real roles (no 'tab', 'menuitem', 'listitem' exist):                        # ACT-1
      tab  := role in {radiobutton,button,group} with Click|Toggle, within 2 levels under 'tablist'
      item := direct child of {list,outline,table,grid} with role in {group,treeitem,row,cell,button}
F3  label(x):                                                                                   # ID-4, ID-5, TXT-4, TXT-9
      row/cell: description or name or join(children text)       (never value)
      textfield: name or value                                    (95.3% are value-only)
      other: name; use description only if != name; never search description in web stacks
      WhatsApp chat row: button.value = "title, preview, time, status"; name is NOT the title  # TXT-5
F4  resolver chain (stop at first unique hit):                                                   # ID-12
      1 native_id, same kind, and tier ok:                                                       # ID-1, ID-2, ID-3
          tier LOW  '^_NS:\d+$'                         -> this session only
          tier SESSION contains a UUID                   -> re-resolve each launch
          React '^(:r[0-9a-z]+:|_r_[0-9a-z]+_)$', '^view_\d+$' -> ignore, not an id
          '<component>:<payload>' with user payload      -> match prefix only
      2 role + norm(label) == norm(sel.name); if >1 take sel.nth (pre-order), confirm by bounds  # ID-6
      3 sel.name empty and role textfield -> match norm(value)                                   # ID-12
      4 walk sel.path (child indexes) from nearest uniquely named ancestor
F5  interactivity filter when choosing among candidates:                                         # ACT-5, ACT-6, ACT-12, TXT-11
      count only {Click,Toggle,Expand,Select,SetValue(on inputs),TypeText}; ignore RightClick, SetFocus
      FW == gecko: ignore Click; use role in {button,link,checkbox,radiobutton,switch,combobox,
                                              textfield,treeitem,menubutton}
      role unknown: Click -> button, no actions -> not interactive
      'readonly': combobox with no value -> button; textfield -> static text
      AppKit/iWork textfield without SetFocus -> label, not input                                # ACT-8
F6  no ref on hit: climb <= 3 ancestors to one with a ref and the needed action, else first ref child   # ID-9
F7  result:
      1 hit   -> return node, node.ref_id
      >1 hit after F1+nth+bounds -> AMBIGUOUS (error, never first-match)                         # ID-7
      0 hits  -> re-run READY once at depth 40, retry F4; still 0 -> NOT_FOUND                   # ID-12
F8  reuse check for stored selectors: named-set overlap (role,norm(name)) vs last run            # ID-11
      < 0.6 -> VIEW_CHANGED, rediscover;  >= 0.9 -> resolve directly
```

**On failure:** `NOT_FOUND` with status TRUST_PREFIX -> scroll the boundary container (ACT flow `SCROLL_TO`) then retry once (LIFE-7). `AMBIGUOUS` -> ESCALATE E5. `VIEW_CHANGED` -> caller rebuilds selectors.
**Measured:** (role,name) unique for 68.1% of named interactives; + bounds -> 98.0%; true duplicates 4/1294 = 0.31% (ID-6, ID-7).

---

## 4. ACT: semantic vs keyboard vs coordinate

**Input:** node from FIND, intent in `click | toggle | expand | select | type(text) | scroll_to`, `FW`, READY status.
**Output:** the call made + `mode` in `SEMANTIC | KEYBOARD | COORD`.
**Laws:** ACT-2,3,4,7,8,9,10,11; ID-7, ID-8; LIFE-5, LIFE-6; WIN-4, WIN-5; TXT-11.

```
A0  if status == TRUST_READ_ONLY (hidden window): activate, re-snapshot, re-FIND              # LIFE-5, G2
    ref must belong to the current snapshot                                                   # ID-8
A1  offscreen node:                                                                           # ACT-11
      'ScrollTo' in actions -> ScrollTo, re-snapshot, re-FIND
      else nearest ancestor scrollarea|browser with Scroll -> Scroll, re-snapshot, re-FIND
      (AppKit: 0/3181 offscreen nodes have ScrollTo; Catalyst has Scroll on leaves)
A2  actionable check:                                                                         # ACT-7
      'disabled' in states -> stop, return DISABLED
      role button and 'Click' not in actions -> not actionable (Safari/Qt drop Click when disabled)
A3  SEMANTIC (default):
      toggle: role in {checkbox,radiobutton,switch} or 'Toggle' in actions -> Toggle          # ACT-2
      expand: combobox -> Expand; menubutton without Expand -> Click                          # ACT-3
      select item: Click the item, or Select on nearest {list,outline,table,combobox} ancestor # ACT-4
      click: Click
      type:
        'readonly' in states or AppKit textfield without SetFocus -> refuse (label)           # TXT-11, ACT-8
        'TypeText' in actions -> TypeText                                                     # ACT-9
        else native with SetFocus -> KEYBOARD (A4) or SetValue for a whole-field replace
A4  KEYBOARD: SetFocus node -> synthesized keystrokes -> VERIFY
      use when: native text entry (TypeText on 2/1596 AppKit fields, 0 in iWork/Word/Qt)     # ACT-9
                or no semantic verb fits the intent
A5  COORD (last resort), only if ALL hold:
      bounds from THIS snapshot (not cached, not a thumbnail, not WS if bounds_source=AX_ROOT) # LIFE-6, WIN-4, WIN-5
      'offscreen' not in states                                                               # ACT-11
      not area0                                                                               # ID-7
      window not hidden (activate first)                                                      # LIFE-5
    click at bounds center
A6  after any mode: G2 (drop bounds, re-snapshot), then VERIFY
```

**On failure:** action error or no change in VERIFY -> try the next mode once (SEMANTIC -> KEYBOARD -> COORD), then ESCALATE E4.

---

## 5. VERIFY: read back the result

**Input:** intent, target selector (not ref), expected value.
**Output:** `PASS | FAIL | UNVERIFIABLE`.
**Laws:** ID-8, ID-11, TXT-1,2,4,6,7,8,10,12, ACT-10, LIFE-6.

```
V0  re-snapshot (same READY depth); re-FIND the target by selector, never by old ref            # ID-8
    overlap < 0.6 vs pre-action named set -> the view changed (expected for navigation, else FAIL)  # ID-11
V1  write-only surface?                                                                        # TXT-8
      has a TypeText node and < 50 chars of name+value in the main region
      (window minus side strips < 300px wide and bars < 60px tall) -> UNVERIFIABLE -> ESCALATE E6
V2  by intent:
      type    : PASS iff 'value' key now present and norm(value) == norm(typed)                # TXT-1
                never compare against name; name stays the placeholder/label                   # TXT-7
                document editors: the doc is one big value on one textfield; check the line   # TXT-12
      toggle  : v = value; v in {'0','1'} -> checked = (v=='1');                               # TXT-10
                else 'checked' in states; else UNKNOWN -> UNVERIFIABLE
                (value equal to the label text = a tab, read as text)
      read    : statictext -> name or value (never both, they repeat)                          # TXT-2
                cell/row -> description or name or children text                               # TXT-4
                heading -> name (value is the level 0-4)                                       # TXT-6
      focus   : > 3 focused nodes -> real focus is the focused list/outline/table container    # ACT-10
                else deepest focused node
      click/expand/select: expected child/state/view appears in the fresh tree
V3  never check coordinates across the action (window may have moved)                          # LIFE-6
```

**On failure:** `FAIL` -> one retry of ACT in the next mode. `UNVERIFIABLE` -> ESCALATE E6 (screenshot/OCR check).

---

## 6. CLASSIFY: guess the framework from the tree

**Input:** skeleton snapshot + default full snapshot (depth 10). No bundle inspection needed.
**Output:** `FW` in `opaque | chromium-family | gecko | wkwebview | hybrid | qt | custom | native`.
**Laws:** LIFE-3, LIFE-8, STR-1, STR-5, ID-1, ACT-13.

```
C0  n == 1 and root.subtree_truncated and ref_count == 0                   -> opaque           # LIFE-8
C1  skeleton n == 7 and root has 4 children                                -> chromium-family  # LIFE-3
C2  wa = webarea(full); p = roles of nodes between root and wa             # STR-1
      p all 'group'                          -> chromium-family
      'tabpanel' in p                        -> gecko
      'tablist' in p                         -> wkwebview
      other intermediates                    -> hybrid (native host + embedded web; Zoom)
C3  no webarea:
      ax_identifier on >= 70% of nodes and >= 50% of those have >= 2 dots -> qt               # ID-1 (OBS 94%)
      >= 5 nodes with role 'row'                                           -> custom (C++ / Office)  # ACT-13
      else                                                                 -> native (AppKit/SwiftUI/Catalyst/iWork)
C4  Electron vs Chromium browser (both chromium-family):                   # STR-2
      shell (nodes outside webarea) <= 12 -> Electron; else browser (Brave 49 shell nodes)
      at depth 10 husk: Electron 19-25 nodes, browsers 51-56                                  # LIFE-3
```

**Replay (python3 over raw JSON, `codex/tmp/classify_replay.py`):** 24/24 on default `full.json`; 20/21 on `forced.json` (the miss is Zoom, whose forced capture is a different window with no webarea, so `native` is correct for that window, LIFE-11).
**Caveats:** tuned on the same 24 apps. The qt rule rests on 1 app (OBS 58/62 ids; Music 15/47 fails the 70% gate). The custom rule rests on Word (13 rows); the next highest is OBS 5, already caught by C3-qt. Native sub-types are not split: in ACT use the rules that are safe for all of them (require Click and not disabled; SetFocus test on textfields).
**Downstream uses of FW:** READY depth (STR-3), FIND scope (STR-2), Gecko Click rule (ACT-5), AppKit textfield rule (ACT-8), TypeText presence (ACT-9), ScrollTo vs Scroll (ACT-11), description search (TXT-9), noise budget (STR-5: > 0.45 Electron, < 0.15 native).

---

## 7. ESCALATE: AX -> handshake -> CDP -> keyboard -> vision

**Input:** the failing procedure, its status/error, `FW`.
**Output:** next channel to use, or `GIVE_UP`.
**Laws:** LIFE-1, LIFE-7, LIFE-8, LIFE-9, LIFE-11, LIFE-12, STR-9, TXT-8, ID-7, ACT-9.

Rung 1: **AX, deeper.** Before leaving AX:
```
E1  frontier or maxd == depth     -> recapture depth 40 / drill frontier refs (not a wait)   # LIFE-1, LIFE-2
E2  RefMap overflow               -> SPLIT by frontier refs                                  # LIFE-9
    complete=false prefix         -> scroll/search inside AX, never drill                    # LIFE-7
```

Rung 2: **handshake.** Caller does nothing. agent-desktop sends `AXManualAccessibility` by itself, only when the tree is complete, has no webarea, and ended above `--max-depth` (retries 25 -> 400ms). No capture in the corpus met that gate, and every Chromium husk was explained by depth alone. Do not add waits or re-activation for "hydration" (LIFE-1, LIFE-12). **There is no caller trigger for this rung.**

Rung 3: **CDP (UNTESTED, no corpus data).** Only for `FW == chromium-family`. Triggers:
```
E3  after depth 40 + frontier drills + SPLIT the tree still has frontier or RefMap overflow
E5  FIND returns AMBIGUOUS inside a webarea (true duplicates, 0.31% of named interactives)  # ID-7
E6  VERIFY is UNVERIFIABLE on a webarea surface (write-only detector)                       # TXT-8
    requires the app started with a remote-debugging port; if not available, skip to rung 4
```

Rung 4: **keyboard.** Triggers:
```
E4  ACT: no semantic verb fits, or SEMANTIC failed VERIFY once
    native text entry with no TypeText (SetFocus + keystrokes)                               # ACT-9
    navigation to items outside a complete=false prefix (in-app search / arrow keys)         # LIFE-7
```

Rung 5: **vision (screenshot + OCR/click).** Triggers:
```
E7  READY returned NON_AX:
      opaque root (n==1, subtree_truncated, ref_count==0)  - give up on AX at first capture  # LIFE-8
      APP_UNRESPONSIVE with loaded_count 0 and count_changed false                          # LIFE-8
      n <= 12 after one activate + 2s + recapture                                            # LIFE-11
      subtree boundary with 0 children and no drill_result (that region only)               # STR-9
E6  VERIFY UNVERIFIABLE and CDP not available                                                # TXT-8
E5  AMBIGUOUS and CDP not available
    vision actions follow A5 rules: activate first, fresh bounds only                        # LIFE-5, LIFE-6
```

`GIVE_UP` only when vision also fails. Corpus rate of hitting rung 5 at READY: 1/24 (Telegram).

---

## What this playbook does not know

- CDP rung: no measurement at all.
- Handshake: never observed firing in this corpus.
- LAW-WIN/ACT/ID/TXT/STR laws were never adversarially verified; most apps had one capture of one screen.
- SPLIT remedy for RefMap overflow was never run (LIFE-9).
- CLASSIFY qt and custom rules each rest on a single app.
