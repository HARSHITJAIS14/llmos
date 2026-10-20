# Hosted vision-provider benchmarks

Model: `qwen/qwen3.8-27b` through OpenRouter. Uses `OPENROUTER_API_KEY` from an explicitly supplied dotenv file. Keys are never written into results. Requires Python and Pillow; uses the standard-library HTTP client with persistent HTTPS connections.

```sh
python screen_understanding/providers/benchmark_openrouter.py \
  --env-file /Users/harshit/Desktop/YC/.env \
  --output screen_understanding/providers/runs/NEW_NAME \
  --mode vision --providers ModelRun Cerebras DeepInfra --repeats 3
```

Default image tasks: eight numbered controls with browser context, and a compact summary of the original full screenshot. `--tasks single_icon` tests a one-word answer for a single search-icon crop. This reduced task is not equivalent to full-screen perception. `--mode smoke` runs the provided two-turn reasoning example, authenticating both calls and passing the assistant's reasoning_details back unmodified.

Vision tests explicitly disable reasoning and pin providers with fallbacks disabled. Streaming records headers time, first visible text, total response time, actual provider, finish reason, usage and raw chunks. No automatic retry or concurrency is used. Prompt JSON is not enforced with provider-specific constrained decoding, so output format is validated afterward. Total measured request time includes network, routing, upload and generation; it excludes preparing images and encoding the JSON body. The first call to each provider establishes a new HTTPS connection. Three repeats are only a small exploratory sample, not a tail-latency benchmark. Different providers may use different quantization and image processing.

Results from 2026-10-18: [visual report](runs/qwen-vision-01/report.html), [summary JSON](runs/qwen-vision-01/summary.json). 27 vision calls plus 2 text smoke calls; all completed, API-reported total cost $0.016253105. All 18 structured vision responses parsed successfully; all nine single-icon answers were Search. No tested vision request completed within 500 ms. The fastest was a 543 ms single-icon request. ModelRun's contextual labels were broadly correct on these eight controls; Cerebras confused sidebar and tab overview, while DeepInfra varied on tab overview.

Rebuild the report after these runs with `python screen_understanding/providers/render_report.py`; it performs no API calls. The current renderer expects the recorded run folders. Raw smoke responses contain provider-returned reasoning metadata, which is preserved for the requested continuation test but is not displayed in the report.

Official references:
- https://openrouter.ai/qwen/qwen3.8-27b
- https://openrouter.ai/docs/guides/routing/provider-selection
- Model/provider endpoint snapshot is saved alongside the report.

## Jev direct vision test

`benchmark_jev.py` reads `TYPESAFE_API_KEY` from an explicitly chosen dotenv file and calls `https://api.typesafe.ai/v1/systemone` with model `jev-1.14.0`. Images use the documented assets map and `TypeSafe-Danger-Zone-Images: true` header. A key was found in `arc-cua/.env`; it was not copied into artifacts.

```sh
python screen_understanding/providers/benchmark_jev.py \
  --env-file /Users/harshit/Desktop/YC/arc-cua/.env \
  --output screen_understanding/providers/runs/NEW_JEV_NAME --repeats 3
```

Image preparation enforces the direct API limits: 280–1568 pixels per side and at least 78,400 total pixels. Small images are padded, large images downscaled. Mapping metadata is retained. Eight fixed-choice questions share one contextual image; a separate full-screen request asks for three present targets and one absent target with both Box and Noul questions. The model was not given existing target coordinates during grounding. No AX tree or previous predicted icon labels are supplied. No desktop actions occur.

[Visual report](runs/jev-direct-vision-02/report.html). Nine successful image calls: eight labels median 809 ms, grounding median 1271 ms, single-icon median 427 ms. Three of nine completed within 500 ms. Sidebar and tab-overview confusions remain. Absent-target probability was near zero in all repeats; Box still returned coordinates, which were not used as valid targets. This is a small exploratory sample, not proof of calibration or a worst-case latency guarantee. One initial image-format rejection is retained separately.

References: https://docs.typesafe.ai/images and https://docs.typesafe.ai/primitives/box

## Populate every detector box with Jev (perception only)

`jev_perception.py` assigns each detected box a role, function, surface (browser/application/embedded content), parent region, and confidence per field. It first proposes screen regions with presence estimates. An annotated image and numeric box coordinates are then shared by 216 typed questions (four per box) in a single request. No clicks, AX data, OCR text or existing captions are supplied. Descriptions are assembled from typed answers; arbitrary prose and exact text transcription are not supported by this schema.

```sh
python screen_understanding/providers/jev_perception.py \
  --env-file /Users/harshit/Desktop/YC/arc-cua/.env \
  --image vlm_testing/click_groq/app_screenshot_raw.png \
  --detections screen_understanding/server/results/omniparser-detector-01/result.json \
  --output screen_understanding/providers/runs/NEW_PERCEPTION_NAME --repeats 3
```

[Perception report](runs/jev-perception-02/report.html), [raw structured result](runs/jev-perception-02/result.json), [evaluation](runs/jev-perception-02/evaluation.md).

Measured on 2026-10-18: 54 boxes, layout API 2.514 s, enrichment/assembly 1.926 / 1.876 / 2.218 s (median 1.926 s), first complete replay 4.618 s. First replay is measured wall clock through first populated result; repeat enrichment reuses layout and the HTTPS connection. All four requests returned HTTP 200. Capture, live detection, detector transfer and report rendering are excluded. Prior detector warm median 58 ms is shown separately; the GPU hostname did not resolve during this run, so saved detections were used. This is one screen and three repeats, not a worst-case guarantee. The 500 ms target is unmet.

Region geometry remains inaccurate. The latest repeat has 22 boxes with at least one unresolved field and 16 parent assignments rejected for insufficient spatial overlap. Raw proposals and confidences remain available. Semantic accuracy needs human labels and broader screens; these unresolved counts are not accuracy scores. Run offline geometry checks with `python -m unittest discover -s screen_understanding/providers/tests`.
