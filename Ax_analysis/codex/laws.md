# How the macOS AX tree actually behaves

**71 behavioral laws mined from 24 apps · ~30MB of captured tree JSON · agent-desktop 0.8.1 · macOS 15, 2026-08-30/31**

Every law was computed over the raw captures in `Ax_analysis/<app>/`, never eyeballed. Each carries evidence with counts, known exceptions, and a **deterministic rule** — an if/then a program can implement with no model in the loop. That is the point of this document: it is the theory layer the fast CUA stands on.

> **Status: PARTIAL.** 6 of 8 planned topics done (windows, roles/actions, identity, text/values, structure, lifecycle). Two topics are still missing (geometry, fingerprint), and **no law here has been through adversarial verification**. Treat confidence labels as the miner's own, not as independent confirmation. See `README.md` §status.

Law ids are `LAW-<DIM>-<n>`. Rules are written as pseudocode against a node with fields `role, name, value, description, states[], available_actions[], bounds{x,y,width,height}, native_id{kind,value}, ref_id, children[]`.

---

## WIN — Windows & ghosts: picking the right window

The single highest-value dimension for a dispatcher: **80.7% of what the window server reports is phantom** (130 of 161 windows across 24 apps).

### LAW-WIN-1 — The ghost predicate (high)
Every ghost shares `visible=false AND is_focused=false AND title==app_name`, combined with one of a small fixed set of geometries. Ghost geometry clusters: 2560×30@(0,0) ×56, 1280×29@(2560,536) ×56, 500×500@(0,940) ×7, 0×0 ×5, 1×1 ×4, 64×64 ×2.

*Exception:* real windows **can** also be invisible with `title==app_name` (Calendar 935×598, Music 980×580, Reminders 768×692, UTM 1393×1410) — the geometry clause is what makes this safe; title+visible alone misfires on 8+ real windows.

```
ghost(w) := (not w.visible) and (not w.is_focused) and (w.title == w.app_name)
            and ( (w.h <= 30 and w.w >= 1000)
                  or (w.w, w.h) in {(0,0),(1,1),(64,64),(500,500)} )
# measured: flags 130/161, zero false positives against AX-root ground truth
```

### LAW-WIN-2 — Menu-bar ghosts come in a quantum of 4 (high)
14 of 24 apps show *exactly* 4 copies of the 2560×30@(0,0) strip and *exactly* 4 of the 1280×29@(2560,536) strip; the other 10 show zero. These 112 strips are 86% of all ghosts. Strip positions encode the display layout.
```
if w.height <= 30 and w.width >= 1000: drop  # no real window is a >=1000-wide, <=30-tall strip
```

### LAW-WIN-3 — `is_focused` is perfect but usually absent (high)
When any window is focused, its bounds equal the AX root bounds **exactly** (6/6 apps, 0px tolerance). But 18/24 apps have no focused window at all.
```
if any(w.is_focused): return it and trust its bounds verbatim   # fast path, not an algorithm
```

### LAW-WIN-4 — `visible=true` is a trap: the thumbnail class (high)
For minimized/other-Space apps the only visible window is a Dock-thumbnail proxy ≤200px in both dims whose bounds lie by **34×–126× in area** but whose *title is the real window's title*. Antigravity 178×161 vs AX 2560×1410 (126× area lie); Firefox 92×108 vs 1249×923; Safari, Brave, VLC, YT Music likewise. Naive largest-visible scores only 8/14.
```
thumbnail(w) := w.width <= 200 and w.height <= 200 and not ghost(w)
# never use a thumbnail's bounds; use its TITLE to identify the window, take bounds from the AX root
```

### LAW-WIN-5 — Window-server bounds are exactly right or wildly wrong (high)
In 9 of 24 apps **no** window-server entry matches the AX root at all. In the other 15 the match is *exact* (tol=0 and tol=5 both give 15/24 — the slack buys nothing). There is no "slightly off" middle ground; minimum area error among mismatches is 34×.
```
if candidate.bounds != ax_root.bounds (exact): the window is minimized/other-Space
    -> take bounds from the AX tree root; treat the WS entry only as a title witness
```

### LAW-WIN-6 — The best-window algorithm (high)
Ghost-filter → focused → largest visible non-thumbnail → largest non-thumbnail. **100% correct on the 15 winnable apps; the other 9 are detectable as the thumbnail/absent class.**
```
candidates = [w for w in windows if not ghost(w)]
if any(w.is_focused): return that w
nonthumb = [w for w in candidates if w.w > 200 or w.h > 200]
pick = max(visible nonthumb, key=area) or max(nonthumb, key=area)
return pick if pick and pick.bounds == ax_root.bounds else ax_root.bounds
```

### LAW-WIN-7 — `title != app_name` proves NOT-ghost (high)
100% of ghosts have `title==app_name`, but so do 10 real windows. Inverted, it is sound: a window whose title differs from the app name is never a ghost (0/31 counterexamples).

### LAW-WIN-8 — Multi-display coordinates are benign (medium)
x range −146…2995. Display 2 at origin (2560,536). Only one negative-x window (a minimized WhatsApp proxy). Derive display rects from the menu-bar-strip ghosts rather than rejecting on coordinates.

### LAW-WIN-9 — Degenerate helper surfaces (high)
`(0,0) (1,1) (64,64) (500,500)` are Chromium/AppKit helper surfaces pinned to screen anchors (500×500 and 64×64 sit at y+h=1440 = display bottom). Smallest real/proxy window in the corpus is 92×108, so dropping these is always safe.

### LAW-WIN-10 — An empty window list ≠ no window (high)
Finder: 9/9 entries are ghosts, yet the AX tree holds a real 920×436 window. Same for Firefox and WhatsApp. **All three had fully successful AX captures.**
```
if no candidate survives the filter: do NOT report "window not found" — snapshot and use ax_root.bounds
```

---

## ACT — Role & action vocabulary: what you can do, per framework

### LAW-ACT-1 — A closed 49-role vocabulary with no `tab`, `menuitem`, or `listitem` (high)
Those concepts always surface under proxy roles: tabs as `tablist > radiobutton` (Brave, Chrome, Discord, Notion, Firefox, Word ribbon) or `tablist > button` (Safari); list items as `list > group` (Finder 1516, Keynote 310), `outline > treeitem` (Gemini 118, Finder 54), `table > row` (Word 26).
```
concept_tab  := descendant (depth<=2) of role=='tablist' with role in {radiobutton,button,group} and Click|Toggle
concept_item := direct child of {list,outline,table,grid} with role in {group,treeitem,row,cell,button}
```

### LAW-ACT-2 — Toggle is an exact biconditional (high)
175 Toggle actions; every node with role ∈ {checkbox, radiobutton, switch} exposes Toggle and **no other role ever does**, in all 13 observed (framework, role) pairs.
```
if role in {checkbox,radiobutton,switch}: Toggle is the activation verb
if 'Toggle' in actions: it is a toggleable control regardless of role name
```

### LAW-ACT-3 — Expand/Collapse are one capability; combobox Expand is universal (high)
Expand count == Collapse count == 83, zero nodes with one without the other. `combobox` → Expand is 100% in every framework. `menubutton` → framework-dependent (absent in Catalyst and Word).
```
if role=='menubutton' and 'Expand' not in actions: fall back to Click (not "non-interactive")
```

### LAW-ACT-4 — Select is a container action, never an item action (high)
All 89 Select actions sit on {list, outline, table, combobox}. **Zero** Select on the 385 treeitem / 454 cell / 31 row nodes.
```
to select an item: Click it, or invoke Select on the nearest {list,outline,table,combobox} ancestor
```

### LAW-ACT-5 — Click is a trustworthy interactivity signal — except in Gecko (high)
Click on non-interactive roles: Gecko **97.1%** (Firefox attaches Click to statictext, toolbars, splitters) vs Electron 0.0%, Chromium 1.5%, AppKit 1.7%, WebKit 4.2%.
```
if framework=='gecko': ignore Click as a filter; rely on role ∈ {button,link,checkbox,radiobutton,switch,combobox,textfield,treeitem,menubutton}
else: 'Click' in actions  =>  actionable
```

### LAW-ACT-6 — RightClick is ambient noise in every web stack (high)
RightClick on static/decorative nodes: Gecko 100%, Electron 96.0%, WebKit 97.2%, Chromium 73.7% vs AppKit 1.7%, iWork 0%. Corpus-wide RightClick (5942) **outnumbers** Click (4606).
```
interactivity score counts only {Click,Toggle,Expand,Select,SetValue-on-inputs,TypeText}
RightClick and SetFocus are ambient — never rank or filter on them
```

### LAW-ACT-7 — Disabled controls keep Click — except in WebKit and Qt (high)
Click retained on disabled buttons: AppKit 27/27, Chromium 6/6, Electron 4/4, Gecko 4/4 — but WebKit-native 12/188 (6.4%) and Qt 0/8. This explains Safari's 210 clickless buttons.
```
actionable(button) := 'disabled' not in states
                      and (framework in {webkit-native, qt} ? 'Click' in actions : True)
```

### LAW-ACT-8 — In AppKit, `textfield` usually means LABEL, and SetFocus is the discriminator (high)
1596 AppKit textfields (37.4% of all AppKit nodes); **99.7% expose SetValue and it means nothing** — Finder's 1516 filename labels and Keynote's 310 navigator labels are not editable. SetFocus separates them: Finder 0/1516, Keynote 0/310 vs Calendar 14/14, VLC 2/2, Reminders 14/16.
```
if framework in {appkit,iwork} and role=='textfield' and 'SetFocus' not in actions:
    treat as statictext — read-only label, NEVER SetValue it
```

### LAW-ACT-9 — TypeText exists only in web-rendered frameworks (high)
100% of Electron and Chromium textfields expose TypeText; AppKit 2/1596 (0.1%), iWork 0/310, Word 0/4, Qt 0.
```
to enter text: if 'TypeText' in actions use it
              elif native and SetFocus present: SetFocus then synthesized keystrokes, or SetValue wholesale
# absence of TypeText on a native field does NOT mean it is not typable
```

### LAW-ACT-10 — Mass-`focused` is a native list-view artifact (high)
A focused NSTableView propagates `focused` to every row: Finder 779/1571 = 751 groups + 27 cells + 1 list. Same shape in Keynote (337/689). Web-rendered captures show ≤4 (the real focus chain).
```
if count(focused) > 3: focus is list-membership noise — the real focus is the focused CONTAINER
                       (role list/outline/table), not its focused item children
else: the deepest focused node is keyboard focus
```

### LAW-ACT-11 — Offscreen recovery is framework-split (high)
ScrollTo on offscreen nodes: Electron 100%, Gecko 100%, Chromium 84.6%, WebKit 83.3% — vs **AppKit 0/3181** (Finder alone has 3042 offscreen nodes). Native apps put Scroll only on the enclosing scrollarea. Catalyst (WhatsApp) is the exception: Scroll on leaf items.
```
if 'ScrollTo' in actions: invoke it
else: walk ancestors to nearest role=='scrollarea'|'browser' with Scroll; scroll it; re-snapshot
NEVER coordinate-click a node with 'offscreen' in states
```

### LAW-ACT-12 — The `unknown` role is bimodal, decidable by action set (high)
27 observations. Actionable cluster: Zoom's 6 nav-rail tabs (uniform 84×50, named, [Click, RightClick]). Inert cluster: Safari banner, Calendar, Notes, Reminders cells — no actions at all. No unknown node anywhere carries SetValue/Toggle/Expand.
```
if role=='unknown': 'Click' in actions ? treat as button : drop from interactive index (keep name as parent's label)
```

### LAW-ACT-13 — Role histograms fingerprint the toolkit (medium)
AppKit is textfield-heavy (37.4%); web-rendered is group-heavy (40–55%); custom C++ (Word/Zoom) is the only class emitting `row` at scale; Catalyst inflates cell+treeitem (44.6% combined); Qt is button-dominated (58.1%).

---

## ID — Element identity & selectors: how to address a thing

### LAW-ID-1 — `native_id` is a bonus, never a primary key (high)
Coverage on interactives ranges 0.1%–94.3%: OBS 94.3%, Safari 88.2%, Chrome 75.0%, Firefox 50.6% — but Finder **0.1%** (1/798), Word 0.0%, Claude 0.0%. By framework: Qt 75%, Gecko 50%, Chromium 25.7%, Electron 16.4%, AppKit 5.0%. Zoom and YT Music emit *both* kinds in one tree.
```
if native_id: use as first key, QUALIFIED BY KIND (ax_identifier and ax_dom_identifier are distinct namespaces)
else: fall through to (role, normalized_name) — expect native_id on <21% of interactives in AppKit/Electron
```

### LAW-ID-2 — `ax_identifier` has three stability tiers (high)
Semantic hand-authored paths (OBS 58/58 full widget paths, Safari 123, Calendar 36) are persistable. `_NS:<n>` Interface-Builder ordinals (VLC 22/22, Reminders 23/35) are build-scoped. Some ids **embed user data**: Safari window ids carry a per-window UUID; Calendar sidebar ids carry the calendar's title.
```
if re.match(r'^_NS:\d+$', v):                       tier LOW      (session only)
elif re.search(r'[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-', v): tier SESSION (re-resolve each launch)
else:                                                tier HIGH     (persistable)
# for '<component>:<payload>' ids, match on the prefix when payload is user content
```

### LAW-ID-3 — Most Electron DOM ids are volatile React auto-ids (high)
React `useId` share: **Notion 90%** (82/91), Discord 83%, Claude 25% — versus 0% in Firefox (`nav-bar`, `back-button`), Chrome (`mainView`), YT Music (`history-link`), Zoom (`sidebar-*`). Chromium's own `view_<n>` is per-launch autogen.
```
reject as persistable if re.match(r'^(:r[0-9a-z]+:|_r_[0-9a-z]+_)$', v) or re.match(r'^view_\d+$', v)
```

### LAW-ID-4 — "Identity lives in value" is the norm, not a Finder quirk (high)
Of 1160 interactive textfields, **95.3% are value-only** (value present, name absent): Finder 765, Keynote 310, TextEdit 20. All 1100 AppKit ones sit under a `group` wrapper with actions {Click, RightClick, SetValue}.
```
label(node) = name if name else (value if role=='textfield' else None)
# but NEVER treat checkbox/scrollbar/slider value as identity — there value is STATE
```

### LAW-ID-5 — Rows and cells are the mirror image: identity in name, never value (high)
287 row/cell/outlinerow nodes: **0 have value**. Name coverage is total in Finder, Calendar, Keynote, TextEdit, VLC, Music — but Gemini 0/60 and OBS 0/5 are unnamed and must be addressed by index or named descendant.

### LAW-ID-6 — (role, name) is NOT unique; bounds make it 98% addressable (high)
Only **68.1%** of named interactives are unique by (role,name). Worst: Calendar 17.9% ('Google' cell ×4), YT Music 50.2% ('Action menu' ×32, 'Like' ×21), Notion 64.6% ('New page' ×6). Adding value+native_id barely helps (413→353 ambiguous); adding **bounds** → 26 remaining (98.0%).
```
candidates = [n for n in nodes if n.role==r and norm(n.name)==name]
len==1 ? done : disambiguate by pre-order index captured at selector-build time, verified by bounds proximity
# never emit a bare (role,name) selector for roles seen in lists: {row, cell, switch, button-inside-row}
```

### LAW-ID-7 — Residual ambiguity is almost all zero-area clones (high)
Of the 26 still-ambiguous elements, 22 have width or height == 0 (20 in Notion: per-row hover toolbars at height 0.0). Genuinely indistinguishable duplicates: **4 of 1294 = 0.31%**.
```
exclude bounds.width<=0 or bounds.height<=0 from resolution; residual multi-match is an ERROR, not first-match
```

### LAW-ID-8 — `ref_id` is strictly snapshot-scoped (high)
All 9046 refs across 67 captures match `^@s[0-9a-z]{11,13}:e\d+$`, embed their own file's snapshot_id (0 mismatches), and are contiguous pre-order ordinals from e1. **71/71 snapshot_ids are distinct** — including back-to-back captures of byte-identical unchanged windows (Calendar full vs forced: same 170 nodes, different sid).
```
a stored selector must NEVER contain ref_id
ref '@S:eN' is usable iff S == current_snapshot.snapshot_id
after ANY action or repaint: re-snapshot, re-resolve by (native_id | role+name | role+value), act on the fresh ref
```

### LAW-ID-9 — Refs are minted for actionable nodes (medium)
100% coverage in 15/23 apps; 176 refs on non-actionable nodes (mostly cells). A node with no actions usually has no ref.
```
no ref? climb to nearest ancestor with ref + required action (<=3 levels), else descend to first ref-bearing child
```

### LAW-ID-10 — Invisible bidi salting hits exactly 3 apps, and stripping is always safe (high)
Scanned every string in every capture for U+200E/200F/202A-E/2066-9/ZWSP/ZWNJ/ZWJ/WJ/BOM/SHY: **WhatsApp 57** (leading LRM on button names/values), **Word 18** (interior, in date-bearing cell names), **Safari 4** (leading). 21/24 apps fully clean. Stripping introduces **0** new collisions across 1294 named interactives.
```
norm(s) = strip invisible-format chars -> NFC -> strip()
apply to BOTH stored selector text and live tree text before every comparison; store selectors pre-normalized
```

### LAW-ID-11 — (role, norm(name)) survives re-snapshot; low overlap detects view change (medium)
Named-set overlap between full and forced captures ≥91% in 17/20 comparable apps. The three failures are all genuine view changes (Chrome different window, Keynote husk→hydrated, Music captured the wrong app).
```
overlap < 0.6  -> VIEW_CHANGED, abort selector reuse, re-run discovery
overlap >= 0.9 -> safe to re-resolve stored selectors directly
```

### LAW-ID-12 — The complete resolver chain (high)
```
resolve(sel):
  1. sel.native_id and tier != LOW-expired  -> match kind + value
  2. role + norm(name)==sel.name, drop zero-area, pick sel.nth (pre-order)
  3. sel.name empty and role=='textfield'   -> match norm(value)          # the 1100+ AppKit item labels
  4. else walk from nearest uniquely-named ancestor by recorded child-index path
  -> return node.ref_id from the CURRENT snapshot for the action call
  on 0 candidates at every tier: re-snapshot once (forced/deep) before failing
```

---

## TXT — Text & values: where readable content lives

### LAW-TXT-1 — Key-absence is the empty signal (high)
agent-desktop **omits** the `value` key entirely when a field is empty: 2455 nodes with non-empty value vs 6 with empty-string. Gemini's composer has no `value` key at all despite exposing SetValue/TypeText.
```
'value' not in node  =>  empty (never distinguish '' from unsupported)
readback after typing: assert the value key APPEARED and equals the typed text — never compare against name
```

### LAW-TXT-2 — Web stacks mirror statictext into both name and value (high)
name==value for statictext: Discord 108/108, Firefox 37/37, YT Music 307/307, Notion 161/163. Qt puts text in name only.
```
read_statictext(n) = n.name or n.value        # never concatenate; they duplicate
```

### LAW-TXT-3 — AppKit list item text is `textfield.value` under scrollarea>list>group (high)
Finder 765/765, Keynote 310/310, TextEdit 20/20 — name empty, actions [Click, RightClick, SetValue], values 2–214 chars. **These are display cells, not inputs**, despite advertising SetValue. Real editors (Notes, Notion body) sit outside that chain and add TypeText+SetFocus.

### LAW-TXT-4 — cell/row never carry value (high)
Corpus-wide: cells 0/235 with value (165/235 with name); rows 0/20 with value **and** 0/20 with name.
```
read_cell(n) = n.description or n.name or join(read(c) for c in n.children)
read_row(n)  = join over children
```

### LAW-TXT-5 — WhatsApp packs a structured record into button.value (medium)
11/11 chat rows are `role=button` with an LRM-marked, comma-joined value: [title, preview (may be multiline, up to 18 newlines), h:mm timestamp with U+202F, sender/status]. Value lengths 32–856. **`name` is the last-message sender label, not the chat title.**

### LAW-TXT-6 — `heading.value` is the LEVEL, not the text (high)
All 18 heading values corpus-wide are single digits 0–4; text is in name. Calendar day buttons similarly: value = bare day number, name = "26, Sunday, July".

### LAW-TXT-7 — An empty field's name IS its placeholder; name never changes on input (high)
Empty-value fields carry prompt names ("Ask Gemini", "Search with Google or enter address"). Filled fields keep the label in name and put content in value.
```
verify fills via value ONLY; any name-equality check after typing is a bug
```

### LAW-TXT-8 — The write-only-surface detector (high)
Gemini's 222-node tree has **zero** text nodes in the transcript region — only sidebar buttons (78) and 2 composer labels. The entire center region has no container at all.
```
write_only(window) := has a node with TypeText
                      and sum(len(name)+len(value)) over nodes inside the main content region
                          (window minus sidebars <300px and strips <60px) < 50 chars
-> route verification through screenshot/OCR, not the tree
```

### LAW-TXT-9 — `description` is native-only and 92% redundant (high)
430 description nodes; 394 identical to name; **zero** in Discord/Notion/Claude/Antigravity/Brave/Chrome/Firefox. Where it differs it is Qt tooltip text (OBS: name='Float', desc='Undocks and re-attaches…') or AppKit summaries with counts.
```
use description only when != name; never search it in Electron/Chromium — it does not exist there
```

### LAW-TXT-10 — Toggle state is the string '0'/'1' in value (high)
Music/YT Music switches 41+2, Firefox 5/5, Calendar checkboxes 9/9, Notion radiobuttons 14. The `checked` state key appears on only 44 nodes corpus-wide vs 99 switches alone. **Exception:** some AppKit tab-style radiobuttons put their visible label text in value instead.
```
checked(n): v=n.value; v in ('0','1') ? v=='1' : ('checked' in states ? True : UNKNOWN)
# value text equal to the label means it is a labeled tab — read as text, not state
```

### LAW-TXT-11 — `readonly` marks display chrome, never a fill target (high)
Notion exposes 33/33 comboboxes as readonly, name-only, button-like ("New page", "Share", "Filter"). Zoom uses a readonly textfield for a marketing banner; Reminders for a section header.
```
'readonly' in states -> exclude from typeable targets
  role=='combobox' and no value -> treat as a BUTTON (Click/Expand), name is its label
  role=='textfield'             -> static display text
```

### LAW-TXT-12 — A whole document is one giant value on one node (high)
Notion's page body: a single name-less textfield at depth 15 with a **2311-char / 267-newline** value carrying the entire page, actions [RightClick, ScrollTo, SetValue, SetFocus, TypeText].
```
document node := deepest textfield with TypeText+SetFocus, no name, len(value) > 2x any sibling text node
-> its value IS the document; split on '\n' for blocks
```

---

## STR — Tree structure & depth: what shape these trees are

### LAW-STR-1 — The root-to-webarea path fingerprints the framework (high)
Chromium-family reaches the webarea through a pure chain of **unnamed groups**: Discord window>group×6>webarea (depth 7), Notion ×7 (8), Claude ×6 (7), Antigravity ×6 (7), Brave ×7 (8), Chrome ×5 (6). Firefox inserts `tabpanel`+`scrollarea` (depth 5). YT Music (WKWebView) inserts `tablist` before `scrollarea` (depth 6).
```
walk window -> first webarea:
  all intermediates unnamed 'group'      -> Chromium-family (Electron or Chromium browser)
  path contains 'tabpanel'               -> Gecko
  path contains 'tablist' before scrollarea -> WKWebView / Safari web app
  no webarea at all                      -> native toolkit surface
```

### LAW-STR-2 — Electron's shell is a constant ~10–12 nodes (high)
Discord 10 of 507 (98.0% under webarea), Notion 12 of 1004 (98.8%), Claude 12, Antigravity 10. Only 9 of 265 Electron interactives sit outside the webarea, all at depth 1 (window controls). Real browsers differ: Brave shell 49, Firefox 67 (actual chrome UI).
```
Electron: find the webarea, traverse only its subtree; outside it, only depth-1 window buttons
Browsers: additionally scan shell nodes for chrome controls
```

### LAW-STR-3 — Interactives live in framework-specific depth bands (high)
**Native is shallow: across all 15 native captures the maximum tree depth observed is 9.** AppKit interactives p10=2, median=6, p90=8, max=9 (91.8% in depth 2–8). Word/Zoom median 2, max 7. OBS everything at depth 1–2. **Electron is deep:** p10=16, median=21, p90=26, max=26 (webarea-relative median 14).
```
native (no webarea) -> capture max_depth=10, never traverse deeper  (0 of ~2700 interactives exceeded depth 9)
web-rendered        -> navigate to webarea first; a depth-10 absolute cap ALWAYS amputates content
```

### LAW-STR-4 — Wrapper chains ≥3 occur only in web content (high)
Maximal runs of single-child unnamed structural nodes: AppKit 1124 chains, **1123 of length 1**, max 2. Electron 411 chains, 24.6% of length ≥2, max 5. Firefox max 4, Chromium max 4.
```
any run of >=3 single-child unnamed groups -> web content
when flattening for an LLM: collapse every such run into its terminal node (lossless for name/role/bounds)
```

### LAW-STR-5 — Structural-noise ratio stratifies toolkits cleanly (high)
Qt 1.6% → AppKit 7.8% → custom C++ 10.9% → WKWebView 30.5% → Chromium 37.2% → Gecko 43.4% → **Electron 54.0%**.
```
noise = count(role in {group,generic,unknown,layoutitem} and no name) / total
noise > 0.45 -> Electron ; 0.25-0.45 -> web content ; < 0.15 -> native toolkit
budget tokens as total*(1-noise) meaningful nodes after wrapper collapse
```
*Exception:* AppKit windows dominated by per-item group wrappers (Finder list view, NSOpenPanel) reach 47% — disambiguate via LAW-STR-4 (chains stay length 1) and absence of a webarea.

### LAW-STR-6 — **Depth-cap truncation is SILENT** (high)
This is the trap that invalidated our own first census pass. YT Music's default capture: 437 nodes, `complete=true`, `truncated=null`, **zero** `subtree_truncated` markers — yet 248 childless nodes sit exactly at depth 10, and the forced capture of the same window has 975 nodes reaching depth 12. Same in every web-class default capture. All 15 native captures have 0 nodes at depth 10.
```
after any capture: count leaf nodes at depth == requested max_depth
if count > 0: the capture IS depth-capped regardless of complete=true -> recapture deeper or drill those leaves
complete/truncated flags must NEVER be used to rule out depth capping
```

### LAW-STR-7 — `complete=false` means enumeration loss, never depth capping (high)
Exactly the 6 `complete=false` apps expose `nodes_observed` exceeding delivered: Finder 2417/1599, Keynote 1072/689, Safari 229/157, Gemini 230/222, Reminders 103/88, Telegram 1/1 (window advertises 56 AXChildren, delivers 0). All 18 `complete=true` apps omit the field — including depth-capped YT Music.
*Exception:* Safari and Gemini lose 72 and 8 nodes with **zero** markers — loss can be unmappable.

### LAW-STR-8 — Truncation markers form one root-to-boundary path (high)
Finder: exactly 6 markers at depths 0–5 tracing window>group>group>browser>scrollarea>list; the **deepest** marked node is the real boundary, and its `drill_result` says why.
```
descend into the child with subtree_truncated==true; deepest marked node = boundary
  drill_result=='TIMEOUT'      -> content exists, enumeration timed out (retry/drill that ref)
  no drill_result, 0 children  -> OPAQUE (Telegram-style; no retry will help)
  many children                -> partially enumerated container
```

### LAW-STR-9 — After forced capture, residual truncation has only two shapes (high)
All Electron/browser/WKWebView forced captures have **0** residual markers (Discord 507, Notion 1004, YT Music 975, Firefox 288 — fully enumerated). Residuals are only: (a) giant homogeneous AppKit item lists (Finder 765 items, Keynote 303, both group>textfield pairs), (b) opaque nodes advertising children and delivering zero (Telegram).
```
boundary is a list/outline with >100 children of one repeating pattern
  -> sample the first ~20 for the item schema, treat the rest as homogeneous rows; do not drill
boundary delivers 0 children with no drill_result -> mark surface OPAQUE, fall back to non-AX
```

### LAW-STR-10 — Native trees are shallow trunks with one dominant fan-out (medium)
Median branching among non-leaves is 1, but every window has one node whose child count dwarfs the rest: Finder list 765, Keynote panel 303, Gemini outline 60, Calendar 42, Safari 42.
```
in a native tree: find max-child-count node; interactives are its children/grandchildren at 1-2 uniform depths
repeated-row containers: item depth = container_depth + 2 (group wrapper + payload)
```

### LAW-STR-11 — An NSOpenPanel is structurally indistinguishable from Finder (high)
Keynote's open panel has the exact 6-level chain Finder has — window>group>group>**browser**>scrollarea>list. The role `browser` appears **only** in these two captures (3 occurrences corpus-wide).
```
role=='browser' at depth ~3 under unnamed groups -> a Finder-style file browser, regardless of host app
-> drive with Finder heuristics; do NOT assume you are looking at the app's main document UI
```

### LAW-STR-12 — Verify capture provenance from inside the JSON (high)
`music/forced.json` has `data.app == 'YT Music'` and the same window id as `yt_music/forced.json` — a mislabeled duplicate that silently double-counted YT Music in earlier stats.
```
before analyzing any capture: assert data.app == intended app AND data.window.id is unique across the corpus
```

---

## LIFE — Lifecycle: when is the tree ready

The short answer: **waiting and focus almost never help.** The "husk" is the depth cap, not an unloaded renderer. Only two things are timing-related: a launch splash window (Keynote) and nothing else. Full data: `lifecycle_laws.json`.

### LAW-LIFE-1 — The Electron/Chromium husk is the depth cap, not a cold renderer (high)
The default depth-10 tree is an exact prefix of the depth-40 tree; every new node hangs below a depth-10 frontier node. Path+role match: Notion 19/19 (985/985 new nodes under 3 frontiers), Claude 19/19, Brave 56/56, Firefox 93/93, YT Music 415/437. Discord: 481 of 482 new nodes under the one frontier. Each frontier's `children_count` equals the forced child count exactly. Nodes at depth ≤10, default vs forced: Discord 25/27, Notion 19/19, Brave 56/56, Chrome 51/51 — nothing near the top "filled in". agent-desktop only sends AXManualAccessibility when the tree has no webarea and ended above the cap; all 8 web-stack captures fail that gate.
*Exception:* Chrome untestable (forced hit a different window, 9/51 paths). Pre-activation captures were overwritten, so an earlier-enabled AX mode can't be fully ruled out.
```
if has_webarea and (any children_count > len(children) or max_depth == max_depth_arg):
    recapture same window with --max-depth 40 (or snapshot --root each frontier ref)
    do NOT activate or wait; expect a strict superset
```

### LAW-LIFE-2 — The untrusted-capture predicate: 10/10, 0 false positives (high)
Label = forced/default ratio ≥1.3, opaque, or overflow. Positives: Discord 20.3x, Notion 52.8x, Claude 1.89x, Chrome 1.35x, Brave 3.04x, Firefox 3.10x, YT Music 2.23x, Keynote 76.6x, Antigravity (overflow), Telegram (opaque). 12 negatives range 0.66–1.05 (clean gap). The census `is_husk` (offscreen + <4 names) catches only 2/10. "No named node in webarea" recall 0.70. Adding `complete=false` adds 2 FPs (Finder, Reminders).
*Exception:* 22 labeled apps is small; OBS and Music excluded. Skeletons always have frontiers — run on full snapshots only.
```
untrusted(s) := any((n.children_count or 0) > len(n.children))
                or total_nodes <= 12
                or (root.subtree_truncated and ref_count == 0)
# never use offscreen counts or name counts as husk signals
```

### LAW-LIFE-3 — The Chromium shell fingerprint: 7-node skeleton, 4 root kids (high)
6/6 Chromium-family apps (Antigravity, Brave, Claude, Discord, Chrome, Notion) give an exact 7-node skeleton (5 unnamed, root 4 kids, max depth 3); 0/16 others do. Depth-10 full: 3 unnamed 16×16 traffic-light buttons + a group chain to a focused webarea at depth 7–8. Electron husks 19–25 nodes, 77–88% unnamed; browsers 51–56. Husk offscreen nodes are all zero-height (Discord 1248×0, Claude 600×0, …).
*Exception:* Firefox (Gecko) and YT Music hit the frontier without this skeleton — the frontier rule catches them.
```
if skeleton.n == 7 and root_kids == 4: chromium_shell -> skip depth 10, capture at --max-depth >= 30
# forced web trees reached depth 12-30 (Brave 16, Discord 25, Notion 30)
```

### LAW-LIFE-4 — Native trees are fully ready in the background (high)
Never-activated vs foreground depth-40: Safari 157→157 (157/157 text and bounds), VLC 57→57, Calendar 170→170, UTM 31→31, Notes 49→49, Reminders 88→88. Activated natives also match: Finder 1571→1599 (1571/1571 text), TextEdit 129/129, Gemini 212→222, WhatsApp 48→48. Covers AppKit, SwiftUI, Catalyst, custom C++ (Zoom, Word), Qt (OBS 62=62). Activation adds 0–5% nodes and 0% text change.
*Exception:* Telegram (opaque), Keynote (launch splash), Zoom forced is a different window.
```
if no webarea and complete and max_depth < max_depth_arg and n > 12:
    trust background snapshot for reading; do not activate just to read
```

### LAW-LIFE-5 — `offscreen` means hidden window, not unready tree (high)
Safari background: root offscreen, 157/157 nodes offscreen; foreground same window 51/157, content 157/157 identical. VLC 53/57 → 0/57, WhatsApp 5/48 → 0/48. All 3 had only a thumbnail-proxy window entry. Finder is 96% offscreen in both modes from scrolling, but has `complete=false`.
*Exception:* long scrolled lists saturate offscreen without being hidden.
```
hidden_window := 'offscreen' in root.states or (offscreen/n >= 0.9 and complete)
if hidden_window: trust names/values; activate + re-snapshot before any coordinate action
# fired 3/24 default captures, 0/21 foreground forced
```

### LAW-LIFE-6 — Bounds and root role are per-snapshot (high)
Same content, bounds equal: Notes 0/48 (moved to display 2), TextEdit 0/129, Reminders 0/87, Word 0/103, Gemini 34/209; unchanged in Safari, VLC, Calendar, UTM. Root role flipped dialog→window in Calendar, Music, Notes, Reminders, UTM (node counts equal); WhatsApp window→dialog. Names and values never changed.
```
after any activate / open -a / Space switch: drop cached bounds, re-snapshot before coordinate actions
treat root role in {window, dialog} as equivalent; never gate trust on it
```

### LAW-LIFE-7 — Enumeration-limit truncation is a stable prefix; don't retry (high)
Delivered/observed, default → forced: Finder 1571/2374 → 1599/2417, Safari 157/229 → 157/229, Reminders 88/102 → 88/103, Gemini 212/220 → 222/230. Delivered share stable (Finder 66%→66%). `snapshot --root` drills on the boundary: 0/7 succeeded (Keynote 3/3, Reminders 4/4 TIMEOUT), each up to 45s.
*Exception:* Gemini and Safari lose nodes with no marker.
```
if not complete and nodes_observed > n:
    trust delivered nodes; no retry/activate/drill
    reach the rest by scrolling the marked container or in-app search, then re-snapshot
```

### LAW-LIFE-8 — Telegram's opaque root is fixed; give up on the first capture (high)
4 captures over 20.5 min (background, foreground depth 40, warm after 17s settle) are identical: 1 node, window, focused, `subtree_truncated`, `_NS:13`, `ref_count=0`. list-surfaces: APP_UNRESPONSIVE, total_count 56, loaded_count 0, count_changed false. No other app has n=1 or ref_count=0.
```
if (n == 1 and root.subtree_truncated and ref_count == 0)
   or (APP_UNRESPONSIVE and loaded_count == 0 and not count_changed):
    stop AX for this app now -> app API or vision
```

### LAW-LIFE-9 — "RefMap exceeds 1MB" is a size limit; split, don't retry (medium)
Antigravity forced: INTERNAL `RefMap exceeds 1MB size limit on write`; retry without `-i` failed the same way. Its depth-10 tree had 5 frontiers, all with ref_id; 202/202 web frontiers corpus-wide have ref_id. Largest successes: Notion 995 refs (1,074,609 bytes), YT Music 968, Finder 831.
*Exception:* the scoped-drill remedy was never run on Antigravity.
```
on INTERNAL with 'RefMap': no same-scope retry, keep -i
snapshot depth 10, then snapshot --root <ref> --max-depth 40 per frontier ref
(or step depth 10 -> 20 -> 30, keep the largest that succeeds)
```

### LAW-LIFE-10 — Window-targeting errors are fixed by re-targeting, not waiting (medium)
`window_without_accessibility_element` = window listed but no AX element. Finder, Gemini, TextEdit had ghost pre-activation best windows (2560×30 strips, a 678×64 sliver) and gave full trees after activation. `AMBIGUOUS_TARGET`: Firefox `--app` matched 11 processes.
*Exception:* no preserved instance of the first error; cause inferred from code and ghost targets.
```
window_without_accessibility_element -> re-list, ghost-filter, retry; then activate + --surface focused
AMBIGUOUS_TARGET -> pick the pid owning the window; always address by --window-id, never --app
```

### LAW-LIFE-11 — The only real timing hazard is the launch transient (medium)
Keynote right after launch: 9-node window w-28256; 15 min later a different window w-28758 with 689 nodes. Web apps gained 0–3 nodes at depth ≤10 over 12–15 min; Telegram 0 over 20.5 min. Extra settle time helped only at launch.
*Exception:* one clear case.
```
after launch: list windows twice ~2s apart; proceed when best window id is stable and n > 12
if n <= 12 and not opaque: wait 2s, re-list, activate, recapture once; still <= 12 -> non-AX
```

### LAW-LIFE-12 — The readiness ladder (high on corpus replay)
Replayed on 24 default captures: TRUST 8 (Calendar, Word, Music, Notes, OBS, TextEdit, UTM, Zoom); R4 depth-frontier 8 (7 reach TRUST after depth 40, Antigravity → RefMap branch); R5 partial prefix 4 (Finder, Gemini, Reminders, Safari); R6 hidden window 3 (Safari, VLC, WhatsApp); R3 unsettled 1 (Keynote); R2 opaque 1 (Telegram). At most 2 snapshots per app; no foreground forced capture misfires.
*Exception:* the handshake rung was never observed; it stays an automatic behavior inside agent-desktop, not a caller step.
```
0) snapshot ghost-filtered best window by --window-id, depth 10 (40 if chromium_shell)
E) errors: no_ax_element -> re-pick + --surface focused; AMBIGUOUS -> pid/window-id;
   INTERNAL RefMap -> frontier drill; APP_UNRESPONSIVE loaded 0 -> R2
R2) n==1 and root.subtree_truncated and ref_count==0 -> GIVE UP (non-AX)
R3) n <= 12 -> re-list, activate, wait 2s, recapture once; still <= 12 -> non-AX
R4) frontier or max_depth == cap -> recapture depth 40 (no activation), back to R2
R5) not complete and nodes_observed > n -> TRUST prefix; scroll/search; never drill
R6) root offscreen or (>=90% offscreen and complete) -> TRUST for reading; ACTIVATE before acting
else TRUST. After any activation, invalidate cached bounds.
```

---

## The ten laws that matter most for a fast CUA

Ranked by how much they change what you build:

1. **LAW-STR-6 + LAW-LIFE-1 — depth-cap truncation is silent, and it is the whole husk.** `complete=true` lies. The Electron "husk" is just the depth cap: recapture deeper, don't wait or activate.
2. **LAW-WIN-6 + LAW-WIN-1 — the best-window algorithm and the ghost predicate.** 80.7% of windows are phantoms; getting this wrong means every downstream step targets nothing.
3. **LAW-ID-8 — ref_id is snapshot-scoped.** Never persist a ref. Re-resolve after every action. This is the single most common way a compiled route rots.
4. **LAW-ID-12 — the resolver fallback chain.** native_id → (role,name)+index → textfield value → ancestor path. This *is* the selector engine.
5. **LAW-ID-6/7 — (role,name) is only 68% unique; bounds take it to 98%.** Selectors need an index; residual multi-match is an error, never first-match.
6. **LAW-ACT-8 — AppKit `textfield` usually means label.** SetFocus is the editability test. Ignoring this makes you "type" into 1516 Finder filenames.
7. **LAW-STR-3 — native ≤ depth 9, web ≥ depth 16.** Sets the capture budget: depth 10 for native is complete and cheap; for web it always amputates.
8. **LAW-ACT-2/4/11 — Toggle is a biconditional, Select is container-level, offscreen recovery is framework-split.** The action-selection core.
9. **LAW-LIFE-12 + LAW-LIFE-2 — the readiness ladder and the untrusted-capture predicate.** Sorts every capture into trust / recapture deeper / navigate prefix / activate first / give up in ≤2 snapshots; the predicate is 10/10 with 0 FP.
10. **LAW-STR-1/5 — root-to-webarea path and noise ratio fingerprint the framework from the tree alone.** The dispatcher must pick a strategy before it knows the app.

---

## What is NOT here (be careful)

- **No adversarial verification.** The verify phase was cut mid-run. These are one analyst's computations per dimension — well-evidenced, but uncontested.
- **Two dimensions never mined:** geometry (can you trust bounds/coordinates), fingerprint (the framework classifier as a tested procedure). Structure and roles cover *some* fingerprint ground incidentally (LAW-STR-1, LAW-STR-5, LAW-ACT-13).
- **Single-capture bias.** Most laws rest on one capture per app, often of a splash/login/idle surface. Keynote's numbers are a "What's New" splash; Claude's are a sign-in page; Safari's are the native Start Page (no webarea at all).
- **One corrupted input, now known:** `music/forced.json` is actually YT Music (LAW-STR-12). Any stat above that cites "music" forced data is suspect; `music/full.json` is genuine.
