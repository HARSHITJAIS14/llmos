# Does our perception context help downstream models?

2026-10-19. Completed API tests using Gemini 3.1 Flash-Lite, Gemini 3.5 Flash-Lite and TypeSafe Jev 1.14.0. No flagship/Pro models, no desktop actions and no new training or annotation campaign.

## Decision

**This pilot does not establish a net perception benefit from our short labels.** Keep the stage optional; it has not earned its current preprocessing/inference overhead as a mandatory dependency of the harness. This does not establish that region context can never help: the baseline already answers nearly all the selected choice questions correctly, and this is a small selected sample.

## Controlled setup

Six saved screens: Appearance, Screen Time, a Bluetooth settings window on a desktop with Stage Manager previews/widgets, Finder Applications, a Chrome loading/blank viewport, and a Terminal Git error/uptime session. Each has six manually checked multiple-choice perception questions and two manually checked target-location references.

Three conditions per screenshot, using the same image bytes and questions:

1. Image alone.
2. Image plus raw OmniParser proposals with neutral IDs and numeric coordinates.
3. Image plus the identical proposals and actual `micro-train-v3/best` short labels.

The 229 supplied boxes are raw detector proposals. No teacher-added regions, teacher descriptions, teacher semantic names or reference answers are passed as hints. The student was run directly on these proposal boxes, including uncertain/noisy proposals, rather than selecting only its correct outputs. Screenshots were identically resized to the provider-compatible maximum edge of 1,568 pixels in all conditions. Models were told to verify imperfect auxiliary labels against pixels.

Requests are independent with no cross-request conversation. Condition order is counterbalanced across six screenshots. Choices use shuffled option IDs; scoring is deterministic against references inspected before requests. This is a downstream utility experiment on saved screens, not a blind generalization test of the student: some application screenshots were in its training set. It is not an end-to-end agent task-completion evaluation.

## Choice-question results

| Model | Image only | + Boxes | + Boxes and labels |
|---|---:|---:|---:|
| Gemini 3.1 Flash-Lite | 35/36 | 34/36 | 34/36 |
| Gemini 3.5 Flash-Lite | 35/36 | 33/36 | 33/36 |
| Jev 1.14.0 | 35/36 | 35/36 | 35/36 |

Compared with boxes alone, labels repaired one Gemini 3.1 choice answer and worsened another; the other two models had unchanged choice outcomes. Compared with images alone, no tested model had a net choice-answer gain. There is little headroom at a 35/36 baseline. One call per case/condition does not separate stable effects from provider nondeterminism; no significance claim is warranted.

Examples:

- In the Bluetooth desktop screen, Gemini 3.1 says On with the image alone and with boxes, then Off with labels. The blue switch is visibly on; its student label is Window Icon.
- In Finder, Gemini 3.5 reads Calendar as 13.1 MB from pixels alone but answers 6 MB with boxes, and retains that answer with labels. This is a metadata-condition regression, not specifically attributable to the captions.
- In Chrome, Gemini 3.5 identifies the X control as Stop loading from pixels alone but calls it Reload completed page in both augmented conditions. A student label on that control says Reload; attribution to the label alone is not established because boxes alone also changes the answer.
- In Appearance, Gemini 3.1 gets the green maximize control wrong with boxes alone, then corrects it with labels. Hints can help individual answers even though aggregate scores do not improve.

## Location questions: exploratory and format-confounded

The Gemini APIs did not consistently follow the requested 0–1 xyxy coordinate contract. The report preserves strict original scores and separately scores 0–1000 numeric outputs after division by 1000. This unit conversion is fixed for all such Gemini outputs; axes are never swapped or chosen to fit a reference. It cannot resolve cases where models confuse axis order.

| Model | Image point hits | + Boxes | + Boxes and labels |
|---|---:|---:|---:|
| Gemini 3.1 Flash-Lite | 9/12 | 9/12 | 10/12 |
| Gemini 3.5 Flash-Lite | 3/12 | 0/12 | 5/12 |
| Jev 1.14.0 | 10/12 | 10/12 | 10/12 |

Point hit means the center of the returned box falls inside the reference box. IoU and raw coordinate-format violations are in summary.json. Some Gemini location results improve with labels, but coordinate-format inconsistency and twelve targets make this insufficient evidence of improved perception. Do not present these numbers without the format caveat.

The final two requests per tested model used one additional eight-target numbered-region diagnostic, avoiding free-coordinate responses. Every model scored 8/8 with and without hints. However, question ordering aligns with the region IDs, permitting an ordering shortcut, so this diagnostic is not strong independent grounding evidence. It is kept in the report rather than hidden or used to claim a gain. Future tests should independently shuffle question and region-ID order.

## Tokens and timing

Mean input-token counts reported by each provider (image accounting differs across providers):

| Model | Image only | + Boxes | + Boxes and labels |
|---|---:|---:|---:|
| Gemini 3.1 Flash-Lite | 1,634 | 3,452 | 3,600 |
| Gemini 3.5 Flash-Lite | 1,634 | 3,452 | 3,600 |
| Jev 1.14.0 | 5,630 | 7,785 | 8,123 |

Most of the added token cost comes from the coordinate/ID metadata, with a smaller increment for short labels. This encoding can be compacted; it is the actual tested representation, not an optimal lower bound.

Median API request times:

| Model | Image only | + Boxes | + Boxes and labels |
|---|---:|---:|---:|
| Gemini 3.1 Flash-Lite | 7.10 s | 14.86 s | 5.57 s |
| Gemini 3.5 Flash-Lite | 4.96 s | 5.27 s | 7.08 s |
| Jev 1.14.0 | 2.38 s | 2.42 s | 2.17 s |

These are six single requests per cell, with variable network/provider latency and initial connection costs. They do not establish a stable speedup or slowdown. They exclude capture, detection and our student inference; those costs must be added for the augmented end-to-end pipeline unless results are already cached. The earlier roughly 3.4-second 50-box student-stage measurement has not disappeared.

## Budget and artifacts

Each tested model received 18 main requests plus two diagnostic requests: **20 each**, with automatic retries disabled. Two retired Gemini 2.5 model names each rejected a single initial request with 404 despite appearing in model listing; no retries were made on those names. Total: 60 successful test requests plus two rejected requests. No quota-error key rotation was used.

- `report.html`: images, references, answers and scores for every condition.
- `cases.json`: frozen questions and visually inspected references.
- `student_boxes.json`, `raw_box_records.jsonl`, `raw_predictions.json`: exact supplied metadata and provenance.
- `responses/`: per-request raw responses, normalized scores, original strict scores, usage and timings. Credentials are not stored.
- `attempts.jsonl`: main request ledger; `discrete/` contains the final six diagnostic records.
- `summary.json`: aggregate and matched helped/hurt counts.

## Handoff recommendation

Use the screenshot as the core perception input for the harness. Add stable element IDs/boxes where the action interface needs them, but keep generated captions optional. Do not schedule more training merely because the dataset grew. A subsequent utility test should use harder, independently sampled screens, independently shuffled discrete target IDs, repeated trials, and actual task completion/verification. Only retain the caption stage by default if that test shows enough benefit to justify its measured overhead.
