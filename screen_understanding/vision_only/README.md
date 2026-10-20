# Recursive vision-only perception prototype

The current experiment uses pixels only. It implements global interpretation, bounded recursive crop inspection, and a final reconciliation pass. It does not use accessibility trees or execute desktop actions.

Visible borders are clues, not assumed region boundaries. The model proposes semantic regions using borders, whitespace, alignment, repeated rows, overlays, and content. There is no independent edge detector in this first version. This lets us evaluate the recursive representation before choosing a detector.

## Run

Requires Python 3.11+ and Pillow. Supply a PNG screenshot at its original resolution and a vision-capable endpoint implementing the chat-completions request/response format.

```sh
# Default: Gemini 3.8 Flash; reads GEMINI_API_KEY or GOOGLE_API_KEY
python pipeline.py screen.png --output runs/gemini --max-regions 6 --max-depth 1 --inspect-all

# Optionally read the key from an explicitly selected dotenv file
python pipeline.py screen.png --output runs/gemini-env --env-file /path/to/.env

# Other compatible providers
python pipeline.py screen.png --output runs/example --provider custom --base-url http://localhost:8000/v1 --model YOUR_VISION_MODEL
```

For custom endpoints requiring authentication, set `VISION_API_KEY` in the environment. The script sends the screenshot/crops to the explicitly supplied endpoint. No model is downloaded, no credentials are discovered, and no network call occurs in the tests.

The source image is preserved at its original resolution. Each regional pass receives a whole-screen overview, the parent region, and a padded original-resolution crop. Image pixels are not enlarged to invent detail. The provider may internally resize/tokenize images; full-resolution input does not guarantee full-resolution perception.

Requests currently run sequentially: root, breadth-first regional analyses, then reconciliation. Each regional request contains several images together; they are not independent parallel calls. Gemini uses low reasoning effort and JSON-object output through its official compatibility endpoint.

Use `--inspect-all` to inspect every proposed region within the depth/count budget, even when the model says no closer inspection is necessary. Without this flag, the model can skip all crops. Malformed JSON receives at most one extra attempt, with both raw responses preserved.

Default bounds: depth 2, at most 12 region analyses, at most 12 proposed children per region. Crops are generated breadth-first so one branch cannot consume the entire budget. Unvisited regions remain explicitly uninspected. The final pass receives the overview and accumulated regional findings; its descriptions remain model hypotheses.

## Outputs

- `source.png`: unchanged-resolution image.
- `crops/`: padded crops plus parent-context images.
- `responses/`: raw structured model responses and per-call latency/usage.
- `tree.json`: region hierarchy, source-pixel boxes, observations, interpretations, uncertainty, coverage, and reconciliation.
- `overview.png`: proposed boxes and IDs over the source.
- `report.html`: standalone local viewer with overview and individual crop contexts.

The JSON is the primary result. The annotated overview is a visualization; generated labels are not fed back as visual evidence in later passes. Model-provided uncertainty is not a calibrated probability. Reconciliation references must resolve to existing region IDs, but valid references do not prove semantic correctness.

## First quality evaluation

Compare full-screen-only against recursive inspection on identical screenshots with reviewed labels. Count omitted elements, wrong region membership, incorrect function claims, invented controls, and crop-induced errors. Record total latency, calls, and tokens. Add refinement or training only where this comparison supports it.

Use cases should include borderless panels, duplicate icons, small text, nested menus, modal overlays, tables, and controls crossing proposed region boundaries. A single screenshot cannot establish hidden content or prove the outcome of an action.

Run the offline geometry/report tests with:

```sh
python -m unittest discover -s tests -v
```

This is an experiment harness, not a validated perception model. A first live screenshot run and manual assessment are available in [evaluation](runs/gemini-live-05/evaluation.md) and [report](runs/gemini-live-05/report.html).

Gemini integration and geometry/report tests pass (10 total). The first recursive live run completed with 6 calls, 73.94 seconds of API wait, and 23,132 tokens; see the evaluation for limitations. Provider documentation: [Gemini 3.8 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash), [compatibility endpoint](https://ai.google.dev/gemini-api/docs/openai).
