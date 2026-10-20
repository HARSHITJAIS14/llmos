# First live Gemini recursive test

Source: `vlm_testing/click_groq/app_screenshot_raw.png`, 2398 × 1830 pixels. Model reported by API: `gemini-3.8-flash`, low reasoning effort. Credentials loaded from explicitly provided dotenv file; no credentials copied into artifacts.

The successful recursive run used 6 sequential API calls: whole screen, four proposed regions, reconciliation. API wait time summed to 73.94 seconds, excluding local image processing. Usage: 21,210 prompt tokens, 1,922 completion tokens, 23,132 total. These numbers exclude earlier failed/exploratory runs. It produced 24 region nodes including root, with 5 directly analyzed and 19 child proposals left uninspected due to depth limit 1. No malformed-output retry was needed in this final run.

## Manual findings

- Broad page structure and visible channel name, subscriber count, like count, and header controls were identified plausibly and matched the screenshot.
- Browser tab/address bars were mentioned but omitted from the region proposals in this run.
- Several boxes truncate their intended content: search field left edge, title height, channel row height, watermark, and recommendation card bottom edges. Boxes are not yet reliable interaction targets.
- The model called the video “playing”; a still image cannot establish playback state. It also described the truncated description as expanded. These are unsupported or misleading state interpretations.
- Final reconciliation only provides context for root and four first-level regions, not all 24 nodes. Empty conflicts/unknowns does not imply verified completeness.
- One proposed box was rejected as too small/outside its parent. The original response is preserved.

Earlier attempts exposed malformed JSON apostrophe escaping, model-controlled skipping of all crops, and a connection reset. Added a single bounded malformed-output retry and an explicit `--inspect-all` option. Network failures still fail visibly with partial artifacts saved.

This demonstrates end-to-end operation, not superior accuracy over a whole-screen baseline. Next evaluation should compare the same screen and reviewed elements across whole-screen and recursive runs, measuring coverage, box correctness, unsupported claims, latency, and token usage.
