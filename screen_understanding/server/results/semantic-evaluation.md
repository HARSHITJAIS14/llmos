# Semantic perception evaluation — 2026-10-18

Single screenshot: 2398 × 1830 Safari/YouTube page. NVIDIA A40. No desktop actions were executed. This is an engineering baseline, not an accuracy benchmark.

| Pipeline | First prediction | Warm median (3 repeats) |
| --- | ---: | ---: |
| OmniParser V2 detector + EasyOCR GPU (batch 1) + Florence captions | 4.106 s | 2.533 s |
| Same pipeline, OCR batch 64 | 3.342 s | 1.980 s |

Warm batch-64 stage medians: OCR 1.697 s; detector 0.0688 s; merge/crops 0.0207 s; captions 0.1723 s. Stage medians need not sum exactly to total median. Timings include in-memory preprocessing, inference, and postprocessing. They exclude image capture, transfer, disk decoding, model loading and report rendering. GPU stages are synchronized. Runs are sequential with four CPU threads. These figures do not measure changes between screens.

Each run read 97 OCR regions, captioned 20 previously unlabeled crops, and retained 80 merged elements. Batch 64 improved warm total by 21.8%. After matching by type and geometry, both variants retained the same geometry set; four text fields differed and output order changed. This is not proof that batching preserves accuracy on other inputs. OCR confidence is not propagated through the upstream merger in this first harness.

Manual inspection found correct visible strings such as Subscribe, Share, 314 and subscriber count, but also omitted numerals, punctuation errors, and thumbnail-text errors. Captions correctly identified microphone/dictation, notifications, share, download, refresh and overflow in examples. Clear failures included search → Clear; macOS window-control cluster → Color picker; back/forward cluster → Code; profile H → Horton. Some captions assign application-specific functions without supporting context. Objects inside video content are still proposed as UI. Upstream interactivity booleans are assumptions, not validated clickability.

ScreenVLM: the checkpoint defaults to disabled generation caching, so the harness explicitly enables it. Transformers 4.49.0/eager diagnostic: 21.440 s for 512 generated tokens, hit the token cap, 25 completed leaf tags. A separate overlay using the checkpoint's recorded Transformers 4.55.2 with SDPA generated 2,291 tokens in a bounded run lasting 60.519 s total; generation hit the 60-second limit and degraded into repeated text. It contained 35 completed leaf tags and did not provide complete screen coverage. Partial/open tags are excluded from element counts. Interrupted earlier diagnostics have no completed timing samples and are not used in comparisons. No optimized serving-engine benchmark has been performed, so this is not the model's best attainable speed.

The earlier 74-second Gemini run produced regional descriptions and reconciliation, which are richer outputs than OCR and icon captions. Comparing 74 seconds to 1.98 seconds is not an equivalent-quality speedup.

Recommendation: use detector + OCR as the current measurable foundation. Add context-aware semantic interpretation only where needed, verify uncertain labels, and evaluate changed-region refresh separately. Do not treat these results as complete UI understanding or action verification.

Provenance: snapshots and pinned code revisions are recorded in adjacent *snapshot.json files; packages in semantic-environment.txt. OmniParser Florence crop preprocessing follows the inspected upstream utility: 64 × 64 resized crops, do_resize=False, batch 128, max_new_tokens=20, greedy decoding. EasyOCR is used rather than PaddleOCR. Detector parameters: image size 1280, confidence 0.10, NMS IoU 0.10; upstream overlap merge threshold 0.7. This harness instruments the components and merger, not the upstream web service.
