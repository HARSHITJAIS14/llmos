# Latency plan for arc-cua's macOS perception layer

**Written for:** the engineer or agent implementing this. Read §1 and §2 before you
touch any code. §1 overturns the assumption this work started from, and if you skip
it you will spend a week writing a native daemon that saves 0.08% of the time.

Measured on this machine (Darwin 25.6.0, arm64, Python 3.13.5, `arc-cua` @ `57512d4`)
on 2026-09-21. Every number below came from a real run, not an estimate. The scripts
are in §9 — re-run them before and after each phase.

---

## 1. The one thing to understand first

The slow part is **the accessibility tree walk**, not OCR. And it is slow because of
**cross-process IPC**, not because the code is Python.

Three measurements make this airtight:

| what | measured |
|---|---|
| PyObjC bridge overhead (`AXIsProcessTrusted`, no IPC) | **0.96 µs** per call |
| One AX attribute read from Safari | **15 µs** per call |
| One AX attribute read from Finder | **1,228 µs** per call |

Every `AXUIElementCopyAttributeValue` is a synchronous round trip to the target app's
main thread. The bridge contributes ~1 µs of Finder's ~1,228 µs. That is **0.08%**.

So:

- **Rewriting the walker in Swift or Rust will not help.** A compiled walker making
  the same number of AX calls against Finder would also take ~4.8 seconds. The
  language was never the cost.
- **The only fix is making fewer AX calls.** That is exactly what the Rust
  implementation next door does — see `agent-desktop/crates/macos/src/tree/ax_ipc.rs`,
  which uses `AXUIElementCopyMultipleAttributeValues`,
  `AXUIElementCopyAttributeValues` and `AXUIElementSetMessagingTimeout`. It is fast
  because it batches, not because it is compiled.

`arc-cua` currently makes **14 AX round trips per node**. On Finder that is 17 ms
per node, and a 278-node walk takes **4.8 seconds**. The consistency check:
14 calls × 1.23 ms = 17.2 ms/node × 278 nodes = 4.79 s. That matches the measured
4.80 s, which means the cost model is correct and you can predict every change's
effect before making it.

### Work in this order

| # | Phase | Effort | Expected win |
|---|---|---|---|
| 1 | Instrument `observe()` | 1 hour | none — but nothing below is verifiable without it |
| 2 | Stop scanning for modals on every observe | ~30 lines | **−89 ms** per observe on a tiny app; seconds on a big one |
| 3 | Batch the AX attribute reads | ~80 lines | **4.9x** on IPC-bound apps (4,799 ms → 976 ms) |
| 4 | Take OCR and the full walk out of the settle loop | ~120 lines | removes a **3–8x multiplier** on everything above |
| 5 | AX messaging timeout + per-observe deadline | ~15 lines | kills a 6 s worst case |
| 6 | Cache OCR on a pixel hash | ~40 lines | −10 to −110 ms on repeat observes |
| 7 | Prune the walk | ~60 lines | app-dependent; largest remaining win on Finder-class apps |
| 8 | *Optional:* bind `agent-desktop`'s C ABI | days | replaces phases 3/5/7 with someone else's tested code |

Phases 2, 3 and 5 are independent of each other. Phase 4 is the biggest multiplier
but is easiest to verify once 2 and 3 have landed, because the per-observe cost is
then stable.

---

## 2. Measured baseline

### Per-stage cost of one `observe()`

Frontmost app was WhatsApp (a video call window, 28 AX elements, 1 OCR element) —
a deliberately *small* tree, so these are near-best-case numbers:

```
MacOSAXBackend.observe()                          27.3 ms
_collect_modal_ax_elements (no modal present)     89.2 ms   <-- pure waste
ocr.front_window() (CGWindowListCopyWindowInfo)    1.5 ms
_capture_window (CGWindowListCreateImage)         14.5 ms
ocr.observe() [capture + Vision OCR]              26.2 ms
_dedupe_ocr (O(n^2) IoU)                          <0.1 ms
MacOSHybridBackend.observe() [FULL]              147.7 ms
_structural_signature(snapshot)                   <0.1 ms
```

Read that again: **the modal scan costs 3x the AX walk and 3x the OCR.** It runs on
every observe, and it found nothing.

### AX walk, per app

278-node walk with the current 14-calls-per-node code, versus a prototype that
batches the attribute reads into one call:

| app | nodes | current | batched | speedup |
|---|---|---|---|---|
| Finder | 278 | **4,798.7 ms** | 976.1 ms | 4.9x |
| Safari | 37 | 11.8 ms | 5.3 ms | 2.2x |
| System Settings | 118 | 174.6 ms | 469.1 ms | **0.4x — slower** |

System Settings got *slower* when batched. Do not treat the batch as a guaranteed
win; it is a per-app question. Re-measure on the apps `examples/` actually drives
(Spotify, System Settings) before and after. The likely cause is that its AX server
handles a multi-attribute request worse than separate ones; §5 Phase 3 tells you how
to fall back per app.

### Attributes are nearly free; calls are not

Cost of one `AXUIElementCopyMultipleAttributeValues` by batch size (µs):

| app | 4 attrs | 11 attrs | 20 attrs | 11 read separately |
|---|---|---|---|---|
| Finder | 1,233 | **1,220** | 1,844 | **13,391** |
| Safari | 31 | 45 | 130 | 183 |
| System Settings | 147 | 305 | 697 | 828 |
| Antigravity IDE | 23 | 40 | 117 | 178 |

Asking for 11 attributes costs the same as asking for 4. **Add attributes freely;
never add calls.** The 20-attribute row is more expensive only because it includes
`AXChildren`, `AXPosition` and `AXSize`, which are costly to serialize.

### OCR, per window

| window | pixels | capture | OCR fast | OCR accurate | texts |
|---|---|---|---|---|---|
| WhatsApp (call) | 800x642 | 28.9 ms | 9.4 ms | 75.0 ms | 1 |
| WhatsApp (chat) | 1087x803 | 10.2 ms | 25.4 ms | 166.8 ms | 53 |
| Antigravity IDE | 2560x1410 | 19.6 ms | 109.6 ms | 507.4 ms | 181 |
| Antigravity IDE | 2560x1410 | 11.2 ms | 63.8 ms | 351.2 ms | 124 |

OCR at `fast` level costs **10–110 ms**, and capture **10–30 ms**. The premise this
work started from put OCR at 200–400 ms and capture at 30–50 ms. Both were high.
OCR is a real cost and worth fixing (phases 4 and 6), but it is an order of magnitude
below the AX walk. Keep `recognition_level="fast"`: `accurate` is 5–8x slower for no
benefit the policy can use.

### Caveats on these numbers

- One machine, one moment, 3 samples per cell. Medians reported.
- No Finder browser window was open, so the 278-node Finder walk was the desktop
  icon view. That is a legitimately slow surface, but it is not "a Finder window".
- Cold vs warm matters: first calls showed spikes (`front_window` 1.5 ms median but
  320 ms max). Always report medians and maxima together.
- Do not cite the "native Rust snapshot of Finder = 110 ms" figure if you see it
  anywhere. That run returned `AMBIGUOUS_TARGET` (9 Finder windows) and never walked
  a tree. It is an error path, not a benchmark.

---

## 3. Why one action takes 3–4 seconds

The per-observe cost above gets multiplied by the settle loop in
[runtime.py:63-112](src/arc_cua/runtime.py#L63-L112).

For `TYPE_TEXT` ([runtime.py:70-72](src/arc_cua/runtime.py#L70-L72)):
`minimum_wait_s = 0.65`, `timeout_s = 2.5`, `poll_s = 0.12`.

The loop calls the **full** `backend.observe()` on every poll
([runtime.py:97](src/arc_cua/runtime.py#L97)) — AX walk, modal scan, window capture
and Vision OCR, every time. It exits only when
`elapsed >= minimum_wait_s and stable_frames >= 2`, and `stable_frames` counts
*consecutive identical* signatures, so **three identical observes in a row** are
required.

Three failure modes compound:

1. **Each poll is a full perception pass.** At 148 ms per observe (small app) plus a
   120 ms sleep, three polls is ~800 ms. At 4.9 s per observe (Finder-class), one
   poll already blows the 2.5 s timeout.
2. **The signature often never stabilizes.** `_structural_signature`
   ([runtime.py:318](src/arc_cua/runtime.py#L318)) includes `element.id` for OCR
   elements — and an OCR id *is* a geometry hash
   ([macos_ocr.py:_ocr_spatial_key](src/arc_cua/backends/macos_ocr.py#L771)), bucketed
   at `round(center_x / 12)` and `round(center_y / 8)`. Text that shifts two pixels
   across a bucket boundary changes the id, which changes the signature. The comment
   above `_structural_signature` says it ignores OCR text — it does, but it does not
   ignore OCR *geometry*, which is the part that jitters.
3. **The deadline is checked before the work, not after.** `while perf_counter() <
   deadline` starts a poll at 2.4 s that finishes at 2.9 s, then the record-keeping
   and the next full observe run on top.

Net effect: for anything but a trivial app, **the settle loop reliably runs to its
timeout**, then overshoots it by one full observe. 2.5 s + overshoot + the caller's
own `observe()` lands exactly where the reported 3–4 s is.

That is the whole story. Nothing here needs a new architecture — it needs the loop to
stop doing perception work it does not need.

---

## 4. Root causes, with locations

| # | Cause | Where |
|---|---|---|
| R1 | 14 AX IPC round trips per node: 11 `_attr` calls + `AXUIElementCopyActionNames` + `AXUIElementIsAttributeSettable` + `AXChildren` | [macos_ax.py:234-306](src/arc_cua/backends/macos_ax.py#L234-L306), [macos_ax.py:219](src/arc_cua/backends/macos_ax.py#L219) |
| R2 | A second, independent tree walk for modals on every observe — `_find_modal_roots` BFS (≤400 nodes, 4 IPC calls each) then `_collect_modal_ax_elements` (≤400 nodes, 13 IPC calls each) | [macos_hybrid.py:84](src/arc_cua/backends/macos_hybrid.py#L84), [macos_hybrid.py:742](src/arc_cua/backends/macos_hybrid.py#L742), [macos_hybrid.py:869](src/arc_cua/backends/macos_hybrid.py#L869) |
| R3 | Full capture + Vision OCR on every settle poll | [macos_hybrid.py:109](src/arc_cua/backends/macos_hybrid.py#L109) via [runtime.py:97](src/arc_cua/runtime.py#L97) |
| R4 | No AX messaging timeout, so one unresponsive app blocks for the 6 s system default | absent from [macos_ax.py](src/arc_cua/backends/macos_ax.py) entirely |
| R5 | Settle signature includes OCR geometry, so it may never stabilize | [runtime.py:335-343](src/arc_cua/runtime.py#L335-L343) |

Two smaller ones, worth fixing while you are in there but **not** worth a phase:

- `_frameworks()` is called once per element ([macos_ax.py:235](src/arc_cua/backends/macos_ax.py#L235)). Imports are cached, so this is ~1 µs against a 1,228 µs call. Hoist it for tidiness, not for speed.
- `repr(ref)` is computed twice per node — once for `visited` ([macos_ax.py:211](src/arc_cua/backends/macos_ax.py#L211)) and once in `_stable_id` ([macos_ax.py:353](src/arc_cua/backends/macos_ax.py#L353)). Measured: `repr(ref)` 0.65 µs, `hash(ref)` 0.24 µs. Switching to `hash()` saves ~0.8 µs per node. Irrelevant. **Do not change `_stable_id`** — element ids must stay stable across observes or every freshness guard breaks.

Resist fixing these first because they are easy. They are worth ~0.2 ms on a 4,800 ms
walk.

---

## 5. The work plan

### Phase 1 — Instrument `observe()` (do this first)

Nothing below is verifiable without per-stage timing. Add it permanently, not as
scratch code.

**Change:** in `MacOSHybridBackend.observe()`, time each stage and put the results in
`DesktopSnapshot.context` under a `timings_ms` key. The context already carries
diagnostics ([macos_hybrid.py:180-209](src/arc_cua/backends/macos_hybrid.py#L180-L209))
and is model-visible, so keep it to one small flat dict of integers.

```python
t = {}
t0 = time.perf_counter()
ax_snapshot = self.ax.observe()
t["ax"] = round((time.perf_counter() - t0) * 1000)

t0 = time.perf_counter()
modal_elements, modal_bounds = _collect_modal_ax_elements(self.ax, pid)
t["modal"] = round((time.perf_counter() - t0) * 1000)

t0 = time.perf_counter()
ocr_capture = self.ocr.observe(...)
t["ocr"] = round((time.perf_counter() - t0) * 1000)
# ... and t["total"] at the end
context["timings_ms"] = t
```

Also add an AX-call counter to `MacOSAXBackend` — increment it in `_attr`,
`_action_names` and wherever you add the batch call, reset it at the top of
`observe()`, and expose it as `context["ax_calls"]`. **This counter is the single most
useful number in the codebase.** The cost model is `calls × per_call_ipc_cost`, so
the counter tells you whether a change worked without any timing noise.

**Acceptance:** `examples/macos_ax_probe.py` prints `timings_ms` and `ax_calls`.
Record them for Finder, Safari, System Settings and Spotify. That is your baseline
table — you will compare against it after every phase.

---

### Phase 2 — Stop scanning for modals on every observe

**Why:** 89 ms measured on a 28-element app, and it scales with the tree. It is the
largest single line-item in a small-app observe, and in the common case (no modal) it
returns nothing.

**Where:** [macos_hybrid.py:84](src/arc_cua/backends/macos_hybrid.py#L84) calls
`_collect_modal_ax_elements` unconditionally.
[`_find_modal_roots`](src/arc_cua/backends/macos_hybrid.py#L742) then BFS-descends to
`max_depth = 8` over `max_nodes = 400`, calling `_ax_is_modal` (2 IPC calls: role +
`AXModal`) and `_ax_children` (2 IPC calls: `AXSheets` + `AXChildren`) on each node.
That is up to ~1,600 IPC calls per observe to find something that is almost always
top-level.

**Change:** sheets, dialogs and popovers are children of the application element or
attached to a window as `AXSheets`. They are not buried eight levels deep. Replace
the descent with a single batched probe:

```python
def _modal_seeds(AX, app_ref):
    """One IPC call at app level, one per candidate window. No descent."""
    values = _batch_attrs(AX, app_ref, ("AXFocusedWindow", "AXWindows"))
    windows = []
    focused = values.get("AXFocusedWindow")
    if focused is not None:
        windows.append(focused)
    windows.extend(_ax_values(values.get("AXWindows")))

    seeds = []
    for window in windows:
        attrs = _batch_attrs(AX, window, ("AXRole", "AXModal", "AXSheets"))
        if attrs.get("AXRole") in {"AXSheet", "AXDialog", "AXPopover"} or bool(attrs.get("AXModal")):
            seeds.append(window)
        seeds.extend(_ax_values(attrs.get("AXSheets")))
    return seeds
```

Verified empirically: one `AXUIElementCopyMultipleAttributeValues` on a window returns
`AXSheets`, `AXRole` and `AXModal` together in a single round trip. With no sheet
present, `AXSheets` comes back as an error placeholder — see the trap in Phase 3.

Only call `_collect_modal_ax_elements` when `_modal_seeds` returns something. Cost
with no modal: 1 + (windows × 1) IPC calls, typically 2–4, down from ~1,600.

**Traps:**
- `AXWindows` on an app with many windows is not free. Cap the candidate list (say 8)
  and always include `AXFocusedWindow` first.
- Popovers (autocomplete dropdowns, menu surfaces) are sometimes children of a window
  rather than a sheet on it. If you find a real app where a popover is missed, add one
  extra level of descent for that role only — do not restore the depth-8 BFS.

**Acceptance:** must still detect a real modal. Manual test, and record it in
`tests/`:
1. Open TextEdit, `Cmd+S` → the save sheet appears.
2. `observe()` → `context["modal_active"] is True`, `modal_element_count > 0`, and
   elements are restricted to the sheet.
3. `Esc` → `modal_active is False` and `timings_ms["modal"] < 5` on the next observe.

**Risk:** medium. A missed modal means the policy targets elements behind a blocking
sheet, and the click silently does nothing. That is worse than being slow. Do not ship
this phase without the TextEdit test and at least one System Settings sheet.

**Rollback:** keep the old function; gate the new path behind
`MacOSHybridBackend(fast_modal_probe: bool = True)`.

---

### Phase 3 — Batch the AX attribute reads

**Why:** 4.9x measured on Finder (4,799 ms → 976 ms). Reduces 14 IPC calls per node
to 2–3.

**Where:** [`_element_from_ref`](src/arc_cua/backends/macos_ax.py#L234) and
[`_walk`](src/arc_cua/backends/macos_ax.py#L198).

**Change:** fetch every attribute plus `AXChildren` in one call, and pass the result
into `_element_from_ref` so it does no IPC of its own.

```python
_BATCH_ATTRS: tuple[str, ...] = (
    "AXRole", "AXTitle", "AXDescription", "AXLabel", "AXHelp",
    "AXValue", "AXEnabled", "AXFocused", "AXSelected", "AXExpanded",
    "AXIdentifier", "AXChildren",
)


def _unwrap(value: Any) -> Any:
    """Normalize one entry from AXUIElementCopyMultipleAttributeValues.

    A missing or unsupported attribute does NOT come back as None. It comes back
    as an AXValueRef wrapping an AXError. Passing one to str() yields garbage
    like "<AXValue 0x...> {value = error:-25205 type = 5}".
    """
    if value is None or value is objc.NULL:
        return None
    try:
        if AS.AXValueGetType(value) == AS.kAXValueAXErrorType:  # == 5
            return None
    except Exception:
        pass
    return value


def _batch_attrs(AS: Any, ref: Any, attrs: tuple[str, ...] = _BATCH_ATTRS) -> dict[str, Any]:
    try:
        # options MUST be 0. See traps.
        error, values = AS.AXUIElementCopyMultipleAttributeValues(ref, list(attrs), 0, None)
    except Exception:
        return {}
    if error != 0 or values is None:
        return {}
    values = list(values)
    if len(values) != len(attrs):
        return {}
    return {name: _unwrap(value) for name, value in zip(attrs, values)}
```

Then:

```python
def _element_from_ref(self, ref, element_id, parent_id=None, attrs=None):
    AS, _ = _frameworks()
    if attrs is None:
        attrs = _batch_attrs(AS, ref)          # keeps existing callers working
    role = attrs.get("AXRole")
    if not role:
        return None
    ...
```

`_walk` calls `_batch_attrs` once per node, passes the dict down, and reads children
from `attrs["AXChildren"]` instead of issuing its own `AXChildren` call.

**This is the highest-value correctness trap in the whole document.** Both of these
are verified on this machine:

- With `options = 0`: the call returns `error = 0` and a full-length array. Missing
  attributes are `AXValueRef` objects with `AXValueGetType() == 5`
  (`kAXValueAXErrorType`), wrapping `-25205` (`kAXErrorAttributeUnsupported`) or
  `-25212` (`kAXErrorNoValue`). **They are not None and they are not `objc.NULL`.**
  A naive port produces elements named `<AXValue 0x...> {value = error:-25205...}`,
  which then get sent to the policy as element names. It will not crash. It will just
  quietly poison every decision.
- With `options = 1` (`kAXCopyMultipleAttributeOptionStopOnError`): the call returns
  `error = -25205` and `values = None` for any element missing any requested
  attribute — which is almost every element. Never use `1`.

Two calls remain per node, and neither has a batch form:

- `AXUIElementCopyActionNames` — keep it. Capabilities depend on it.
- `AXUIElementIsAttributeSettable(ref, "AXValue", None)` — 1 extra IPC call per node,
  ~330 ms of a Finder walk. Make it configurable rather than removing it:

```python
MacOSAXBackend(probe_settable_everywhere: bool = True)
```

When `True`, behavior is exactly as today. When `False`, only probe when the batch
returned a usable `AXValue` or the role is in `_VALUE_ROLES`. **This is a
behavior change, not just an optimization**: today
[macos_ax.py:266-268](src/arc_cua/backends/macos_ax.py#L266-L268) adds `SET_VALUE`
for *any* settable element, and the comment there says that is deliberate
("Capability comes from AX itself, not a hard-coded role allowlist"). Gating it
shrinks the legal action space JEV sees, which can change task outcomes. Default it
to `True`, measure the cost, and only flip it if the examples still pass.

**Traps:**
- System Settings measured *slower* batched (0.4x). Keep a per-backend
  `batch_attrs: bool = True` escape hatch and check your app suite. If you find a
  consistent pattern (for example, batching loses on apps whose per-call cost is
  already under ~60 µs), consider auto-selecting: time the first 10 nodes both ways
  and stick with the winner for that app. Only build that if the measurements
  justify it.
- `AXChildren` inside the batch is one of the costlier attributes (batch20 showed
  +50% on Finder when geometry attributes were added). It is still far cheaper than a
  separate round trip. Keep it in.
- Do not add `AXPosition`/`AXSize` to the batch. AX elements do not carry bounds today
  (`DesktopElement.bounds` is None for `source="macos_ax"`), and
  [`_ax_bounds`](src/arc_cua/backends/macos_ax.py#L624) is only called at execute time
  for double/right click. Adding geometry to every node costs ~50% more per call for
  a field nothing reads.

**Acceptance:**
- `ax_calls` per observe drops by ~5x for the same node count. This is the real test —
  it is deterministic, unlike wall time.
- Element *count* and every element's `role`, `name`, `value`, `actions` are
  **byte-identical** to the old walker for at least three apps. Write a throwaway
  comparison script that runs both walkers back to back and diffs
  `[e.compact() for e in snapshot.elements]`. Do not skip this: a silent attribute
  regression here corrupts `semantic_guard()` and therefore every freshness check.
- `pytest` green.

**Risk:** medium-high, entirely because of the error-placeholder trap. The diff test
above retires that risk.

---

### Phase 4 — Take OCR and the full walk out of the settle loop

**Why:** this is the multiplier. Phases 2, 3 and 7 reduce the cost of one observe;
this phase reduces how many times you pay it, from 3–8 down to 1.

**Where:** [`_observe_after_action`](src/arc_cua/runtime.py#L63-L112).

**Change, in three parts:**

**(a) Give the backend an optional cheap probe.** Add to `DesktopBackend` in
[protocols.py](src/arc_cua/protocols.py) — optional, so `StateMachineBackend` and
every test keep working:

```python
class DesktopBackend(Protocol):
    def observe(self) -> DesktopSnapshot: ...
    def is_fresh(self, snapshot, action) -> bool: ...
    def execute(self, snapshot, action) -> None: ...
    # Optional. Runtime falls back to observe() + _structural_signature.
    def settle_probe(self) -> tuple: ...
```

In the runtime:

```python
probe = getattr(self.backend, "settle_probe", None)
if probe is None:
    def probe():
        return _structural_signature(self.backend.observe())
```

**(b) Implement `settle_probe` on `MacOSHybridBackend`.** It must answer only "did
anything change?" — it does not need to produce elements. Default it to a **shallow,
interactive-only AX signature**: the focused window's bounds and title, the focused
element's id and value, plus a batched walk capped at depth 5 and 80 nodes. With
Phase 3 that is ~2 IPC calls per node, so ~3 ms on a fast app.

**Do not default to a pixel hash.** It is tempting — capture is 10–30 ms and hashing
a stride-sampled buffer is ~2 ms, with no AX IPC at all — but a blinking text caret
changes the pixels roughly every 500 ms, so the hash never stabilizes. That breaks
precisely the `TYPE_TEXT` path this is meant to fix. If you do want a pixel signal,
compare with a tolerance (stable when fewer than ~0.1% of sampled bytes differ)
rather than exact equality, and sample every 8th row via the image's bytes-per-row
stride rather than hashing all 14 MB. Treat it as an alternative to measure, not the
default.

**(c) Fix the loop shape.**

```python
started = time.perf_counter()
deadline = started + timeout_s
last = None
stable = 0

while True:
    now = time.perf_counter()
    # Check the budget BEFORE starting work, not after.
    if now + expected_probe_s > deadline:
        break
    signature = probe()
    if signature == last:
        stable += 1
    else:
        last = signature
        stable = 0
    if (time.perf_counter() - started) >= minimum_wait_s and stable >= 1:
        break
    time.sleep(poll_s)

return self.backend.observe()   # exactly ONE full perception pass
```

Three changes in there, each deliberate:

- **`stable >= 1`, not `>= 2`.** Two consecutive identical probes, not three. Probes
  are now cheap enough to run often, so a shorter confirmation window is the right
  trade. Keep `poll_s` small (try 0.04) to compensate.
- **The deadline is checked before the work.** Track a rolling estimate of probe cost
  in `expected_probe_s`, or use the last probe's duration. This removes the overshoot
  described in §3.
- **One full `observe()` at the end.** The loop no longer returns a snapshot it
  happened to have; it returns a fresh, complete one.

**(d) Move the hardcoded constants into `RuntimeConfig`.**
[runtime.py:69-85](src/arc_cua/runtime.py#L69-L85) hardcodes waits per `ActionKind`
inside the method. Move them to a `dict[ActionKind, SettleProfile]` on
`RuntimeConfig` so they are tunable without editing the runtime. Keep the current
values as defaults — `minimum_wait_s = 0.65` for typing exists because
search-as-you-type UIs need time to render results, and dropping it will cause real
failures. Tune it with measurements, per app, later.

**Traps:**
- R5 from §4: whatever signature you use, keep OCR *geometry* out of it. If you fall
  back to `_structural_signature`, fix
  [runtime.py:335-343](src/arc_cua/runtime.py#L335-L343) so OCR rows contribute
  neither `element.id` nor bounds — only a stable count. Otherwise the fallback path
  keeps the never-stabilizes bug.
- `tests/test_settling.py` pins `_structural_signature`'s exact semantics: OCR text
  changes ignored, invisible elements excluded, AX value changes detected. If you
  change what OCR contributes, **update that test deliberately and say why in the
  commit**. Do not delete it.

**Acceptance:**
- A typing action performs **exactly one** full `observe()`. Assert it: count calls
  with a counting backend wrapper in a test.
- End-to-end wall time for `examples/test_spotify.py` and
  `examples/test_settings.py` drops without a change in outcome. Both must still
  reach the same terminal status.
- `pytest` green.

**Risk:** high, and it is the good kind of risk — this phase changes *when* the
runtime believes the UI is ready. A probe that is too coarse returns early, and the
policy then reasons over a half-rendered UI. Validate on Electron apps specifically
(search-as-you-type is the hard case), and keep `minimum_wait_s` as the floor that
protects you.

---

### Phase 5 — AX messaging timeout and a per-observe deadline

**Why:** there is no `AXUIElementSetMessagingTimeout` anywhere in `macos_ax.py`. The
system default is 6 seconds. One unresponsive app blocks a single attribute read for
6 s, and the settle loop's own timeout cannot help because it only checks between
polls. This is a tail-latency and hang fix, not a throughput fix.

**Change:** right after creating the application element in
[`observe`](src/arc_cua/backends/macos_ax.py#L48):

```python
app_ref = AS.AXUIElementCreateApplication(pid)
AS.AXUIElementSetMessagingTimeout(app_ref, 0.5)   # seconds, float
```

Set it on the **application** element — that applies to all messages to that app.
Setting it on a leaf element affects only that element. The Rust implementation does
the same thing with a remaining-budget calculation
(`agent-desktop/crates/macos/src/tree/ax_ipc.rs:64`); copy the idea.

Then add a walk budget. Pass a deadline into `_walk` and stop when it expires:

```python
if time.perf_counter() > deadline:
    context["truncated"] = "deadline"
    return
```

Surface `truncated` in `snapshot.context` so the caller can tell a partial tree from
a small one. A partial tree is a legitimate result; a silent partial tree is a bug.

**Traps:** 0.5 s may be too aggressive for a genuinely busy app — a dropped attribute
becomes a missing element, and a missing element becomes a failed action. Start at
2.0 s, log how often calls actually time out, then lower it with evidence.

**Acceptance:** a deliberately wedged app (pause one with `kill -STOP <pid>`, then
`kill -CONT` it afterwards) no longer blocks `observe()` for 6 s. `truncated` appears
in context.

---

### Phase 6 — Cache OCR on a pixel hash

**Why:** 10–110 ms per observe, and consecutive observes of an idle screen do
identical work.

**Change:** in `MacOSOCRProvider.observe`, hash the captured image and return the
previous `OCRCapture` when `(window_id, pixel_hash)` is unchanged.

```python
provider = Quartz.CGImageGetDataProvider(image)
data = Quartz.CGDataProviderCopyData(provider)
# Stride-sample: hashing all 14 MB of a 2560x1410 window costs ~15 ms.
key = hashlib.blake2b(bytes(data)[::64], digest_size=16).hexdigest()
if (window.window_id, key) == self._cache_key:
    return self._cache_value
```

You still pay the 10–30 ms capture; you skip the 10–110 ms Vision pass.

**Traps:**
- `[::64]` on a `bytes` object copies. Use a `memoryview` and slice rows by
  `CGImageGetBytesPerRow` if it shows up in the profile.
- Cache exactly one entry, keyed by window id. A multi-entry cache invites serving
  OCR from the wrong window, and a stale coordinate is a misplaced click.
- Invalidate on window id change, window bounds change, and pid change.

**Acceptance:** two `observe()` calls on an idle screen — the second reports
`timings_ms["ocr"]` at roughly capture cost only. Elements are identical.

---

### Phase 7 — Prune the walk

**Why:** after phases 2–5, a Finder-class app still costs ~976 ms, and ~2 IPC calls
per node is the floor. The only remaining lever is **fewer nodes**.

This phase is last because it is the only one that changes what the policy can see,
and every pruning rule is a bet about which elements matter. Do it with measurements
from the examples, not from first principles.

Options, cheapest bet first:

1. **Interactive-only mode for the settle probe** (already implied by Phase 4) —
   pure win, the probe does not need names or values.
2. **Skip children of text-leaf roles.** `AXStaticText` has no interactive
   descendants worth the round trips.
3. **Cap per-container children.** A desktop icon view or a long list contributes
   hundreds of near-identical nodes. Take the first N per container and record
   `truncated_children` in metadata so the policy knows more exist.
4. **Drop offscreen nodes** — but this needs `AXPosition`/`AXSize`, which costs ~50%
   more per batch call. Only worth it if it prunes whole subtrees, and measure it
   against the cost.

`max_elements = 1200` and `max_depth = 18`
([macos_ax.py:30](src/arc_cua/backends/macos_ax.py#L30)) are the current caps. With
1.2 ms per call on a slow app, 1200 elements at 2 calls each is ~2.9 s — so **the
existing default cap is itself a 3-second budget.** Lower it to what the policy
actually uses. Check the JEV candidate limit first:
`TypeSafeJevPolicy(max_candidates=240)`
([typesafe.py:81](src/arc_cua/policies/typesafe.py#L81)) already truncates to 240
candidates. Walking 1200 nodes to send 240 is waste. Measure the actual element
counts the examples produce, then set `max_elements` near that.

**Acceptance:** `examples/test_spotify.py` and `examples/test_settings.py` still
reach the same terminal status with the same or fewer actions. If a pruning rule
changes an outcome, revert that rule — it was the wrong bet.

---

### Phase 8 — Optional: bind `agent-desktop`'s C ABI

Only after phases 1–7, and only if the numbers still are not good enough.

There is a tested native implementation next door at
`/Users/harshit/Desktop/YC/agent-desktop`. It already does batched attribute reads,
ranged children reads and messaging timeouts
(`crates/macos/src/tree/ax_ipc.rs`), and it exposes a C ABI.

What you would get:

| symbol | what it gives arc-cua |
|---|---|
| `ad_init(3)` | ABI handshake. `AD_ABI_VERSION_MAJOR` is 3. Abort on mismatch. |
| `ad_adapter_create_with_session("arc")` | long-lived adapter, refmap persistence |
| `ad_snapshot(adapter, app, surface, max_depth, interactive_only, compact, &out)` | full tree as a JSON envelope with `@ref` ids |
| `ad_get_tree_exact(...)` | raw flat BFS tree, no refs, no JSON — the better fit if arc-cua keeps building its own `DesktopElement`s |
| `ad_wait(adapter, &args, &out)` | **native settling**: element-appear, text-appear, window-appear, element predicates. Could replace the Phase 4 loop outright. |
| `ad_execute_by_ref(...)` | ref-based execution with an actionability preflight |
| `ad_screenshot*` + `ad_image_buffer_*` | window capture |

Build and reference material:

```sh
cd /Users/harshit/Desktop/YC/agent-desktop
cargo build --profile release-ffi -p agent-desktop-ffi
# -> target/release-ffi/libagent_desktop_ffi.dylib
# header: crates/ffi/include/agent_desktop.h
# worked ctypes example: tests/ffi-python/smoke.py
# docs: ./npm/bin/agent-desktop-darwin-arm64 skills get ffi
```

Hard constraints, from that skill doc:

- Use `--profile release-ffi`, **not** `--release`. Plain release builds
  `panic = "abort"`, so any Rust panic inside an `extern "C"` function `SIGABRT`s the
  Python host.
- Call `ad_init(AD_ABI_VERSION_MAJOR)` once after load; abort on mismatch.
- Free every returned string with `ad_free_string`, every tree with `ad_free_tree`,
  every image with `ad_image_buffer_free`, every handle with `ad_free_handle` on the
  same adapter that produced it.
- Use the `*_exact` variants. The legacy `AdWindowInfo` / `AdRefEntry` layouts carry
  no process-generation evidence and fail closed by design.
- `ad_screenshot` returns **PNG or JPG**, not raw pixels
  (`AD_IMAGE_FORMAT_PNG = 0`, `AD_IMAGE_FORMAT_JPG = 1`). So do not route Phase 6's
  pixel hashing through it — you would add an encode. Keep arc-cua's own capture for
  hashing.

**Why this is optional and last:** it is a dependency, a build step and an FFI memory
contract, in exchange for work that phases 3, 5 and 7 mostly do in-process. Take it
if you want `ad_wait` and ref-based execution, not for the traversal speed alone.

---

## 6. Ideas deliberately rejected

Each of these was in the original plan. Each is killed by a specific measurement.

**A native Swift or Objective-C daemon to escape the PyObjC bridge.** The bridge
costs 0.96 µs per call. One Finder AX read costs 1,228 µs. The bridge is 0.08% of the
cost. A Swift daemon making 14 calls per node would take the same 4.8 seconds. The
`atree` implementation is not fast because it is compiled — it is fast because
`ax_ipc.rs` batches. **Copy the batching, not the language.**

**`ScreenCaptureKit` / `IOSurface` for zero-copy capture, as a priority.** Capture
measured 10–30 ms, which is 2–8% of a slow observe and about 20% of a fast one. The
estimate that motivated it (30–50 ms, "the GPU copies every frame") was roughly
right about the mechanism and wrong about the magnitude. There *is* a good reason to
do this eventually: `CGWindowListCreateImage` is deprecated from macOS 14, and
[macos_ocr.py:577-587](src/arc_cua/backends/macos_ocr.py#L577-L587) already contains
a comment anticipating the move. Do it for future-proofing, on its own schedule, not
for latency.

**Pixel-hashing as the primary settle signal.** Good instinct, wrong default. A
blinking caret changes the pixels every ~500 ms, so the hash never stabilizes during
typing — the exact case with the longest wait. Keep it as a tolerance-based secondary
signal (Phase 4b).

**Asynchronous OCR on a background thread.** Once OCR is out of the settle loop
(Phase 4) and cached (Phase 6), it runs roughly once per action at 10–110 ms. Threading
it adds a concurrency contract — which snapshot does a late OCR result belong to? —
for a shrinking prize. Revisit only if the post-Phase-6 profile still shows OCR on
top.

**"Get to <100 ms per action."** Qualify this target. For apps whose AX server is
fast (Safari 15 µs/call, Antigravity IDE 14 µs/call), sub-100 ms perception is
reachable after phases 2–4. For Finder-class apps at 1,228 µs/call, two calls per
node means **50 nodes is already 123 ms**. No architecture fixes that in-process —
only walking fewer nodes does. Set per-app-class targets:

| app class | observe now | realistic target |
|---|---|---|
| fast AX server (Safari, Electron) | 50–150 ms | 25–40 ms |
| slow AX server (Finder-class) | ~4,900 ms | 300–600 ms |
| per action, end to end | 3,000–4,000 ms | <400 ms fast, <1,200 ms slow |

---

## 7. Invariants you must not break

The runtime's value is that it is bounded and honest. Speed that costs any of these
is not worth having.

1. **Freshness guards.** `semantic_guard()`
   ([models.py:89](src/arc_cua/models.py#L89)) hashes `role`, `name`, `value`,
   `enabled`, `visible`, `selected`, `expanded`, `parent_id`, `source`. If a batched
   read stops fetching one of those, guards change meaning and stale-target detection
   weakens silently. **If you drop an attribute from the walk, drop it from
   `semantic_guard()` deliberately and say so in the commit.**
2. **Element id stability.** `_stable_id` uses `repr(ref)`
   ([macos_ax.py:353](src/arc_cua/backends/macos_ax.py#L353)). Ids must stay stable
   across observes within a session, or `is_fresh` and every `target_id` break. The
   0.65 µs is not worth the risk.
3. **The agent owns intent.** The runtime never invents text, values or verification
   criteria. `materialize_action` ([validation.py:17](src/arc_cua/validation.py#L17))
   resolves `input_key` against `Subtask.inputs` and nothing else. No phase here
   touches that.
4. **Terminal semantics.** `SUBTASK_COMPLETE` / `BLOCKED` / `NEEDS_AGENT` keep their
   meanings. A faster settle must not turn a real `BLOCKED` into a false completion.
   Note that `no_change_limit = 3` ([runtime.py:33](src/arc_cua/runtime.py#L33))
   infers "blocked" from three unchanged revisions — so anything that changes how
   `revision` is computed changes when `BLOCKED` fires.
5. **`pytest` stays green,** and `tests/test_settling.py` is updated only with an
   explicit rationale.
6. **Partial results are labelled.** A truncated walk sets `context["truncated"]`.
   Never let a deadline produce a tree that looks complete.

---

## 8. Numbers to collect

Record all of these before you start and after each phase, for Finder, Safari,
System Settings and Spotify:

- `ax_calls` per observe — the deterministic one, trust it most
- `timings_ms` per stage: `ax`, `modal`, `ocr`, `total`
- element count, and whether `truncated` was set
- full-observe calls per action (target: 1)
- settle polls per action, and whether the loop hit its timeout
- end-to-end wall time for `examples/test_spotify.py` and `examples/test_settings.py`,
  plus the terminal status of each

Two you do not have yet and should get, because they change the plan:

- **How often is a modal actually present?** If it is more than a few percent of
  observes, Phase 2's fast path matters less than its correctness.
- **How many elements does the policy actually use?** `max_candidates = 240`
  truncates already. If the examples never exceed ~200 elements, `max_elements = 1200`
  is a pure 3-second liability and Phase 7 moves up the list.

---

## 9. Benchmark scripts

Reproduce the §2 tables. Run with the repo venv, which already has PyObjC:
`/Users/harshit/Desktop/YC/arc-cua/.venv/bin/python`. Requires Accessibility **and**
Screen Recording permission for the host process — both were granted on this machine
(`AXIsProcessTrusted()` and `CGPreflightScreenCaptureAccess()` both returned true).

None of these change the frontmost app, so they are safe to run while you work.

### 9a. Per-stage observe cost

```python
import sys, time, statistics
sys.path.insert(0, "/Users/harshit/Desktop/YC/arc-cua/src")
from arc_cua.backends.macos_ax import MacOSAXBackend
from arc_cua.backends.macos_ocr import MacOSOCRProvider
from arc_cua.backends.macos_hybrid import MacOSHybridBackend, _collect_modal_ax_elements

def t(label, fn, n=3):
    s, out = [], None
    for _ in range(n):
        t0 = time.perf_counter(); out = fn(); s.append((time.perf_counter() - t0) * 1000)
    print(f"{label:<44}{statistics.median(s):8.1f} ms  (min {min(s):.1f} max {max(s):.1f})")
    return out

ax = MacOSAXBackend()
snap = t("MacOSAXBackend.observe()", ax.observe)
pid = int(snap.context["pid"])
print("  elements:", len(snap.elements), "app:", snap.application)
t("_collect_modal_ax_elements", lambda: _collect_modal_ax_elements(ax, pid))
ocr = MacOSOCRProvider()
t("ocr.observe() [capture + Vision]",
  lambda: ocr.observe(pid=pid, app_name=snap.application, preferred_window_title=snap.window))
t("MacOSHybridBackend.observe() [FULL]", MacOSHybridBackend().observe)
```

### 9b. Is it the bridge or IPC? (the §1 measurement)

```python
import sys, time
sys.path.insert(0, "/Users/harshit/Desktop/YC/arc-cua/src")
import AppKit, ApplicationServices as AS

def per_call_us(fn, n):
    t0 = time.perf_counter()
    for _ in range(n): fn()
    return (time.perf_counter() - t0) * 1e6 / n

apps = {str(a.localizedName() or ""): int(a.processIdentifier())
        for a in AppKit.NSWorkspace.sharedWorkspace().runningApplications()
        if a.activationPolicy() == 0}
attrs = ["AXRole", "AXTitle", "AXDescription", "AXLabel", "AXHelp", "AXValue",
         "AXEnabled", "AXFocused", "AXSelected", "AXExpanded", "AXIdentifier"]

print(f"{'app':<22}{'1 attr':>10}{'11 sep':>10}{'11 batch':>10}{'ratio':>8}")
for name, pid in apps.items():
    app = AS.AXUIElementCreateApplication(pid)
    AS.AXUIElementSetMessagingTimeout(app, 2.0)
    err, win = AS.AXUIElementCopyAttributeValue(app, "AXFocusedWindow", None)
    ref = win if err == 0 and win is not None else app
    one = per_call_us(lambda: AS.AXUIElementCopyAttributeValue(ref, "AXRole", None), 200)
    sep = per_call_us(lambda: [AS.AXUIElementCopyAttributeValue(ref, a, None) for a in attrs], 50)
    bat = per_call_us(lambda: AS.AXUIElementCopyMultipleAttributeValues(ref, attrs, 0, None), 50)
    print(f"{name[:21]:<22}{one:>10.0f}{sep:>10.0f}{bat:>10.0f}{(sep/bat if bat else 0):>7.1f}x")

# Bridge-only baseline: no IPC at all.
print("bridge only:", per_call_us(AS.AXIsProcessTrusted, 20000), "us/call")
```

### 9c. Confirm the error-placeholder trap before you rely on it

```python
import sys; sys.path.insert(0, "/Users/harshit/Desktop/YC/arc-cua/src")
import AppKit, ApplicationServices as AS, objc
pid = next(int(a.processIdentifier())
           for a in AppKit.NSWorkspace.sharedWorkspace().runningApplications()
           if a.activationPolicy() == 0)
app = AS.AXUIElementCreateApplication(pid)
err, win = AS.AXUIElementCopyAttributeValue(app, "AXFocusedWindow", None)
ref = win if err == 0 and win is not None else app
attrs = ["AXRole", "AXTitle", "AXBogusDoesNotExist", "AXChildren"]
err, vals = AS.AXUIElementCopyMultipleAttributeValues(ref, attrs, 0, None)
print("err:", err)
for a, v in zip(attrs, list(vals or [])):
    print(f"  {a:<22} is_None={v is None} is_NULL={v is objc.NULL} "
          f"AXValueGetType={AS.AXValueGetType(v)} (error type is {AS.kAXValueAXErrorType})")
```

Expected output: `err: 0`, and `AXBogusDoesNotExist` comes back with
`is_None=False`, `is_NULL=False`, `AXValueGetType=5`. That is the trap. Handle it in
`_unwrap` before you trust a single batched value.
