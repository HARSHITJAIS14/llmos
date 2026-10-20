# Reconstructing interfaces from rendering, without accessibility trees

Research review, 19 October 2026.

## Scope and conclusion

The objective is to build our own machine-readable account of an interface from its rendering and observable responses: text, visual elements, positions, cursor changes, hover states, and eventually supported interactions. Accessibility trees and DOM inspection are not inputs to the proposed experiments. Linux is acceptable as a research platform; macOS remains the eventual target. This supersedes the earlier AX-first recommendation for this research direction. Existing implementations have not been changed.

Three conclusions follow from the sources:

1. **Drawing interception is real.** Some rendering interfaces expose strings, glyphs, coordinates, and paint attributes before rasterization. NVDA provides a concrete example of constructing a display model from intercepted drawing operations.
2. **There is no demonstrated universal stream of semantic UI commands at the OS/display boundary.** Modern clients can deliver rendered buffers rather than text or widgets. Owning the compositor grants useful observation and control, but does not restore discarded application structure.
3. **The promising experiment combines rendering provenance with temporal observation.** Recover exact text where the rendering path preserves it; track pixels and interaction responses everywhere else. Determine experimentally whether the extra information justifies the instrumentation.

This document is a source-based feasibility review and experiment design. No hooks, compositor modifications, capture benchmarks, or cross-application cursor tests have been run. Proposed gains and thresholds below are hypotheses, not measured results.

## 1. What the bits actually represent

A simplified pipeline is:

```text
application state and event handling
    → layout, text shaping, paint operations
    → rasterization into images/textures
    → composition of surfaces, effects, and cursor
    → display scanout
```

The precise boundaries vary. Software rasterization, GPU rasterization, cached layers, video overlays, and direct scanout mean there is no single compulsory path with a uniform representation.

For an illustrative 8-bit RGBA image, a pixel stores four channel values. A black pixel may be represented as `(0, 0, 0, 255)`. The value does not say whether it belongs to the letter “A,” a button border, a photograph, or a video. Real capture formats can differ in channel ordering, precision, color space, and alpha representation.

The useful distinction is **decoding a format** versus **recovering lost meaning**. We can decode a pixel buffer exactly once its format is known. Recovering original text, hierarchy, or intent is an inverse problem.

Consider two applications: one draws a live button; the other displays a bitmap of that button at the same coordinates. They can produce identical pixels. Therefore no algorithm receiving only that frame can always distinguish the two. A hover response can distinguish some such cases, but a bitmap application can also implement a matching response. This is an identifiability limit, not a model-size problem.

More formally, if rendered observations are `I = R(S)` and distinct states satisfy `R(S1) = R(S2)`, there is no unique inverse from `I` to `S`. History and interventions shrink the set of plausible states; they do not guarantee complete recovery.

Chromium explicitly describes conversion of painted content into software bitmaps or GPU textures. Wayland explicitly lets clients render into shared buffers and hand those buffers to a compositor. These establish why the OS need not receive original text. [Chromium compositor implementation guide](https://github.com/chromium/chromium/blob/main/docs/how_cc_works.md), [Wayland rendering architecture](https://wayland.freedesktop.org/docs/book/Architecture.html).

## 2. Where interception offers useful information

| Observation point | Evidence available in suitable paths | What remains missing | Research assessment |
|---|---|---|---|
| Text layout/shaping | Source text, font, glyph mapping, positions | Widget role and intended action; visibility after later composition | Best opportunity for exact text |
| 2D paint recording | Text/glyph operations, paths, rectangles, images, clips, transforms, colors | Application semantics; source strings in some operations | Strong candidate for reconstructing visible structure |
| GPU API commands | Resources, draw calls, shaders, texture coordinates | Usually Unicode and control semantics | Useful for provenance; costly as a universal parser |
| Window compositor | Surfaces, transforms, stacking, damage, input routing, cursor surfaces | Internal widgets and source text in client buffers | Best controlled observation laboratory |
| Captured composed frame | Visible appearance and changes | Original operations, hidden state, exact source text | Broad fallback; inference required |
| Display output | Final visual signal | Nearly all higher-level structure | Little semantic advantage over suitable frame capture |

Going lower improves access to some physical facts, but often reduces semantic information. We should intercept the earliest broadly shared boundary that still preserves useful information, then validate against the final visible image.

### Core Text: exact text needs the backing string

Core Text exposes line creation from attributed strings and line drawing. Its glyph runs expose glyphs, positions, and string indices. Apple documents those indices as mappings back to characters in the backing store. **Indices are not the string itself:** a successful observer must preserve the source string and connect it to the run and draw operation. Merely seeing a glyph ID is insufficient. [CTLine](https://developer.apple.com/documentation/coretext/ctline), [CTRunGetStringIndices](https://developer.apple.com/documentation/coretext/ctrungetstringindices(_:_:_:)).

A controlled macOS experiment can instrument a program we build, record line creation and drawing, and retain transforms and clipping. This demonstrates feasibility for that path. It does not establish interception coverage across AppKit, SwiftUI, browsers, games, and arbitrary third-party processes.

### DirectWrite: a particularly explicit boundary

`IDWriteTextRenderer::DrawGlyphRun` receives a glyph run and a description containing character-related properties. It is called through the text layout rendering interface. This is a concrete place to examine text-to-drawing correspondence in a controlled Windows program; it is not a system-wide subscription to all drawing. [DirectWrite callback documentation](https://learn.microsoft.com/en-us/windows/win32/api/dwrite/nf-dwrite-idwritetextrenderer-drawglyphrun).

### Skia and Chromium: inspect paint before it becomes a texture

Skia exposes rectangles, paths, images, and glyph/text drawing operations. `SkTextBlob` carries glyph runs and positioning; some `drawGlyphs` overloads also accept source UTF-8 text and cluster information. Available fields depend on the actual call path. Do not assume every text blob carries recoverable Unicode. [SkCanvas API](https://api.skia.org/classSkCanvas.html), [SkTextBlob API](https://api.skia.org/classSkTextBlob.html).

Chromium has a paint recording component and a later rasterization/composition pipeline. A source-built browser can therefore expose paint operations without consulting its DOM or AX tree. This is renderer instrumentation: it works because we control that binary, not because any OS transparently exposes every browser’s paint records. [Chromium paint component](https://chromium.googlesource.com/chromium/src/+/main/cc/paint/README.md), [compositor component](https://github.com/chromium/chromium/blob/main/cc/README.md).

### Why a glyph-to-character dictionary is not a complete solution

Shaping can merge characters into ligatures, split or rearrange glyphs, and apply contextual substitutions. Font identity matters. HarfBuzz retains cluster information precisely because output glyphs do not simply correspond one-to-one to input characters. Preserve original text and mapping when possible; treat reverse mapping from glyphs alone as potentially ambiguous. [HarfBuzz clusters](https://harfbuzz.github.io/clusters.html), [cluster examples](https://harfbuzz.github.io/a-clustering-example-for-levels-0-and-1.html).

## 3. A working precedent: NVDA’s display model

NVDA’s source contains GDI hooks, including text output and painting operations. Its display model stores text chunks with screen rectangles, baselines, and formatting. The code handles clearing, copying, scrolling, and clipping rather than simply collecting strings forever. This is directly relevant: an observer can reconstruct and maintain an independent representation from rendering activity. [NVDA GDI hooks](https://github.com/nvaccess/nvda/blob/master/nvdaHelper/remote/gdiHooks.cpp), [display model implementation](https://github.com/nvaccess/nvda/blob/master/nvdaHelper/remote/displayModel.cpp).

The limitation is coverage. This evidence supports the technique for intercepted paths; it does not show that legacy GDI hooks cover modern GPU UI, remote video, or every custom renderer. The useful lesson is the mechanism and its state maintenance, not an assumption of universal coverage.

Graphics debuggers provide another ingredient. RenderDoc captures graphics workloads on its supported APIs/platforms; apitrace traces and replays supported graphics API calls. They are tools for investigating what survives in a workload, not ready-made screen-to-text engines. Do not assume RenderDoc supports macOS Metal. [RenderDoc repository](https://github.com/baldurk/renderdoc), [apitrace repository](https://github.com/apitrace/apitrace).

## 4. What hover and cursor changes reveal

The usual causal chain is: pointer movement reaches a target; application or toolkit hit testing chooses a response; cursor state and/or paint changes; the display updates. The OS routes events and composes output, but need not know that an internal region is a search field.

Your observation suggests measuring a response function:

```text
response(region, pointer path, elapsed time)
  = cursor transitions + changed pixels + overlays + timing
```

An observation can say “entering this region repeatedly changes the cursor to an I-beam and darkens this boundary.” The interpretation “text-oriented region” is stronger than a single-frame guess. “Editable input” remains unproven: selectable static text can also use an I-beam. Likewise, gray does not prove disabled, and a hand cursor does not prove that clicking has a particular effect.

Proposed measurement procedure:

1. Record a stationary baseline and its spontaneous changes.
2. Move the pointer into a candidate region; record position and timestamps.
3. Capture immediate and delayed responses, including tooltips.
4. Move out and repeat to test reproducibility and spatial specificity.
5. Separate cursor pixels from content changes where feasible.
6. Store observations separately from inferred roles.

Movement itself changes pixels; caret blinking, animation, and video also change pixels. A temporal difference alone is not proof of hover causation. Damage rectangles are redraw hints, not widget boundaries or exact pixel-difference masks.

Start with passive observation of human interaction. Controlled automatic hover scans belong in test fixtures first: moving the user’s cursor can disrupt their work, and some interfaces trigger actions on dwell. Click/type experiments should use disposable fixtures with known outcomes.

## 5. Platform strategy

### Linux: the strongest first laboratory

Use an instrumented Wayland compositor in a controlled desktop session, together with a source-built rendering client. The compositor gives us surface identity, commit timing, damage information, input routing, and cursor surfaces. It does **not** automatically provide the internal widget tree or text of a buffer. Instrument Skia or another client rendering layer separately to obtain those earlier signals. [Wayland architecture](https://wayland.freedesktop.org/architecture.html), [Wayland protocol specification](https://wayland.freedesktop.org/docs/html/apa.html).

A nested compositor is a practical experimental boundary: it sees the clients launched inside its session, not every unrelated host application. A virtual machine is also useful for reproducibility but requires separate reporting of its graphics path and latency.

Recommendation: build the scientific experiment on Linux if infrastructure is available; do not spend the first phase trying to force identical hooks into every macOS application.

### macOS: supported capture now, renderer coverage as a separate question

ScreenCaptureKit offers captured frames and metadata, with Apple’s sample obtaining an IOSurface from the pixel buffer. Dirty rectangles identify changed/redrawn regions. Cursor inclusion is configurable. These are viable observation inputs independent of an app’s accessibility implementation. They do not expose original text or UI roles. [Apple capture sample](https://developer.apple.com/documentation/screencapturekit/capturing-screen-content-in-macos), [dirty rectangles](https://developer.apple.com/documentation/screencapturekit/scstreamframeinfo/dirtyrects), [cursor inclusion](https://developer.apple.com/documentation/screencapturekit/scstreamconfiguration/showscursor).

Cross-process cursor classification is an explicit experiment, not a solved dependency. Test native, browser, and custom cursors; if a public cursor query is unreliable, classify the captured cursor image. Coordinate scaling, clipping at screen edges, and custom cursor artwork need their own cases.

Instrumentation of arbitrary macOS applications is a different deployment problem. Hardened Runtime library validation restricts which libraries a process can load. Demonstrating a hook in our own program does not imply it can be loaded into every signed application. No reviewed source establishes a public universal WindowServer feed of original strings. That is a bounded research finding, not proof about every private implementation detail. [Apple library validation documentation](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.cs.disable-library-validation).

The macOS destination is a shared reconstruction engine with a supported capture adapter and any renderer adapters whose coverage we can actually demonstrate. Linux results must not be presented as proof of macOS injection feasibility.

### Windows: useful reference implementation and capture metadata

Desktop Duplication exposes desktop image updates, dirty/move regions, and pointer information; pointer shape may need to be handled separately from the image. Combine that documented capture path with a controlled DirectWrite experiment and the NVDA precedent when evaluating the interception hypothesis. [Desktop Duplication API](https://learn.microsoft.com/en-us/windows/win32/direct3ddxgi/desktop-dup-api).

## 6. The representation we should build

Maintain an evidence graph, then serialize it into plain text or JSON. Do not force paint operations into a widget tree: one widget can generate many operations, and a single image can contain many apparent widgets.

Each observation should retain:

- Time, frame/surface identity, coordinate space, bounds, clipping, and transforms.
- Literal captured text when available, with its provenance; OCR text separately identified.
- Visual appearance and changes, including cursor observations.
- Candidate relationships and roles, with confidence and contradictory evidence.
- Persistence across movement, scroll, repaint, occlusion, and surface destruction.

Illustrative output, not a captured result:

```text
Region r17, bounds=(140, 82, 320, 34)
Text: "Search" — captured from an instrumented text draw
Observed: pointer entry changes arrow → I-beam
Observed: border darkens; reverses on pointer exit
Interpretation: likely text-entry or text-selection region
Editable: unknown; no typing test performed
```

Exact source text is not automatically visible text. Paint can occur offscreen, be clipped, be covered later, or feed a texture that is never displayed. We must connect operations to displayed surfaces and visibility; otherwise interception can produce more text but a worse description of the screen.

## 7. Experiments that answer the hard questions

### Experiment A — prove which layer loses which information

Build fixtures rendering the same label as: native text; shaped glyphs; vector outlines; a bitmap; and a video frame. Include clipping, transparency, transformed text, repeated labels, and cached redraws. Include Latin ligatures, Hindi, Arabic, emoji, and combining marks.

Observe at three boundaries: text/paint operations, compositor surfaces, final pixels. Record exactly which fields survive. Ground truth comes from the fixture’s test manifest, held apart from the observer. Do not feed widget labels or AX/DOM state to the reconstruction path.

Success is an auditable table of recovered information and gaps. A failure to recover Unicode from a bitmap is an expected boundary, not a reason to fake an exact answer.

### Experiment B — test whether hover adds information

Construct visually similar editable fields, selectable labels, inert lookalikes, enabled/disabled controls, and custom cursor regions. Compare one frame, passive video, and controlled hover observations. Measure role precision/recall, false claims of editability, and additional observation latency. Include controls with no hover feedback.

### Experiment C — measure the value of renderer access

On identical fixtures and tasks compare:

| Variant | Inputs |
|---|---|
| P | Pixels with OCR/visual parsing |
| T | Pixels plus time and pointer observations |
| R | Pixels plus instrumented paint/text provenance |
| RT | All of the above |

Measure text error, visible-text precision, region localization, state-change accuracy, identity switches, p50/p95 processing latency, CPU/GPU overhead, and dropped updates. Report both instrumented-path performance and uninstrumented coverage. Split test cases by rendering backend and application, not adjacent frames.

Illustrative decision gates: proceed with renderer adapters only if they substantially improve exact-text recovery or latency on relevant applications; proceed with hover probing only if it improves interaction classification enough to justify delay and interference. Set numerical thresholds after establishing baseline measurements.

### Experiment D — port the observation engine to macOS

Keep inference and evidence schemas fixed. Replace Linux capture/input adapters with supported macOS equivalents. Run an owned Core Text application as the exact-text instrumentation case and unmodified apps as capture-only cases. Explicitly report unsupported paths rather than treating broad screen visibility as broad renderer access.

## 8. Open questions and failure conditions

- Can source text be associated reliably with draw records after caching and cross-process transport?
- How often do supported hooks observe text that is actually visible, versus offscreen or discarded draws?
- Can pointer response boundaries identify useful regions without an expensive full-screen scan?
- Do renderer-derived identities survive scroll, animation, and resource reuse?
- How much semantic inference remains even after perfect text recovery?
- Which macOS renderer paths can be observed under ordinary deployment constraints?

Stop pursuing a universal low-level decoder if the experiments show the boundary carries only images. Continue with reconstruction from the information demonstrably present. A GPU trace of textured rectangles is not evidence of hidden Unicode; a color transition is not evidence of a control’s business meaning.

The next concrete deliverable is **an instrumented rendering fixture with synchronized paint, surface, pixel, and pointer records**, followed by the four-way comparison. That will test the central premise before committing to a compositor fork, broad hooking framework, or model training campaign.
