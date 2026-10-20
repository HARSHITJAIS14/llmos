# Jev perception evaluation — 2026-10-18

Vision only, no action execution. Input: the existing Safari/YouTube screenshot and 54 saved OmniParser detector boxes. Screenshot downscaled to 1568×1197 for the direct API. Model: jev-1.14.0. No human icon labels or OCR are supplied.

One layout call has 16 typed questions; one enrichment call has 216 questions sharing the numbered full-screen image and geometry. Three enrichment repeats reuse the layout. Every requested typed answer passed format validation. Returned hypotheses are retained, including confidence, unknowns and rejected parent relationships.

Timing: layout request 2.514 seconds; enrichment plus local assembly 1.926, 1.876, 2.218 seconds; first complete replay wall clock 4.618 seconds. All four HTTP requests succeeded. This excludes live capture, live detection, transfer and report rendering. The prior 58 ms detector measurement is separate. This is not within the requested 500 ms budget and is not a tail-latency benchmark.

Global browser/video-watch categories are correct. Layout boxes are imperfect: the proposed application header omits right-hand controls, and the details region covers the description while missing title/channel/actions. Consequently, 16 parent proposals in the latest repeat are rejected by the 50% child-overlap check. There are 22 boxes with at least one unresolved field. These are uncertainty/consistency measures, not human-scored semantic accuracy.

Icon confusions persist: the browser sidebar toggle can be labeled tab overview, tab overview can be labeled new tab, and video-frame logos/menu graphics can be treated as application interface. Only three boxes in the latest repeat are classified as embedded content, although more depict video content. Grouped detections (back/forward, like/dislike, window controls) cannot provide separate semantics for their constituent controls.

The description is a template over fixed categories. Exact visible text, exhaustive relationships, animation/playback state and confidence calibration are not established. A second stage based on a small number of typed heads is not equivalent to free-form rich understanding. Before expanding scope, compare a one-request reduced schema against these saved results and score known UI controls, embedded content and region coverage on multiple screens.
