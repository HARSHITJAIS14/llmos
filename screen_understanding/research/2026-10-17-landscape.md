# Screen understanding and observable UI changes

Research review — 17 October 2026

## Decision under discussion

The project focus is now accurate screen understanding and observable changes. The existing desktop-agent work is a source of capture, identity, verification, and application knowledge. This review does not start a new executor implementation or training run.

The proposed product boundary is a perception service: screenshots, accessibility observations, optional browser metadata, and observation history enter; a grounded, queryable screen state and an explanation of changes leave. A downstream agent can consume it, but task planning is outside the core scope.

This review uses original papers, author repositories, official model cards, and training documentation. Reported benchmark numbers are authors' results, not local reproductions. Availability means a public artifact was located, not that it has been installed or validated. GPU guidance is an engineering estimate pending the exact GPU model/count and a measured memory test.

## 1. What “rich understanding” should cover

There are at least six distinct targets:

1. **Elements:** location, text, type, appearance, and raw accessibility properties.
2. **Structure:** regions, containers, lists, rows, cards, dialogs, and relationships such as labels-for and belongs-to.
3. **Function:** what a region supports and what an element probably does in its current context.
4. **State:** selected, expanded, disabled, focused, loading, covered, visible, and current values.
5. **Continuity:** which elements persisted, moved, changed, appeared, or left the viewport.
6. **Effects:** whether an observed transition supports the expected result of a prior action.

A system can excel at locating one requested element and still fail at the other five. This is why a grounding leaderboard is insufficient evidence for complete screen understanding.

Also distinguish present observations from inaccessible facts. A screenshot cannot establish the full contents of a virtualized list, a server-side save, an unseen menu, or the precise behavior of an unfamiliar icon. The representation needs “unknown,” inferred hypotheses, and optional requests for further observation.

## 2. Closest prior work

### Screen Parsing: Towards Reverse Engineering of UI Models from Screenshots — 2021

This early work explicitly predicts UI elements, hierarchy, and semantic groups from screenshots. Its formulation is close to the structural part of our objective: a screen contains relationships, not merely boxes. It is useful conceptual groundwork, although an older model should not be assumed competitive on current macOS screens.

Sources: [paper](https://arxiv.org/abs/2109.08763), [author explanation](https://blog.ml.cmu.edu/2021/12/10/understanding-user-interfaces-with-screen-parsing/).

### Screen2AX — 2025

The closest macOS-specific precedent generates accessibility-style trees from screenshots using element detection, OCR/captioning, and group detection. The authors report 77% overall hierarchy F1, but only 31% leaves F1 in the corresponding table. The reported 0.76-second generation measurement excludes element descriptions. Its agent evaluations include target selection; these should not be presented as universal workflow reliability. Native accessibility-derived labels also introduce annotation limitations.

Public code and dataset links exist. It is a strong macOS baseline, not proof that tree generation is solved.

Sources: [full paper and tables](https://arxiv.org/html/2507.16704v1), [repository](https://github.com/MacPaw/Screen2AX), [tree dataset](https://huggingface.co/datasets/macpaw-research/Screen2AX-Tree).

### ScreenParse / ScreenVLM / ScreenParser — 2026

This line explicitly studies dense parsing rather than sparse target annotation. The paper introduces 771K web screenshots and a 316M-parameter structured parser; current model cards describe a v2 dataset with 1,447,100 screenshots. ScreenVLM produces typed, located, transcribed elements in ScreenTag format; ScreenParser is a detector requiring separate text extraction. The authors publish domain-transfer results and acknowledge a web-to-desktop gap.

These are immediate evaluation candidates. A small released checkpoint is a better starting point than recreating its full pretraining run.

Sources: [paper project and evaluation tables](https://saidgurbuz.github.io/screenparse/), [ScreenVLM model and training notes](https://huggingface.co/docling-project/ScreenVLM), [ScreenParser model](https://huggingface.co/docling-project/ScreenParser), [dataset](https://huggingface.co/datasets/docling-project/screenparse).

### OmniParser V2 — 2025

OmniParser combines detection, OCR, and icon descriptions to give a language model grounded screen elements. Code and weights are available. It is useful as a visual detection/captioning baseline, but its flat element representation does not alone supply persistent identity, application state, or action-effect evidence. Our old local latency report should not be generalized to every version or GPU setup.

Sources: [Microsoft introduction](https://www.microsoft.com/en-us/research/articles/omniparser-v2-turning-any-llm-into-a-computer-use-agent/), [repository](https://github.com/microsoft/OmniParser).

### SparkUI-Parser — 2025

The proposed architecture separates semantic processing from continuous coordinate prediction, with a rejection mechanism for nonexistent targets. It is relevant to the cost and accuracy of generating long coordinate sequences. However, the public repository inspected for this review contains the paper announcement/assets and says training and evaluation resources are planned. It is not an implementation-ready baseline based on that repository inspection.

Its “ScreenParse” benchmark is distinct from the IBM/ETH ScreenParse project above; identical names should not lead to mixing datasets or results.

Sources: [paper](https://arxiv.org/abs/2509.04908), [release status](https://github.com/antgroup/SparkUI-Parser).

### UFO2 — 2025

An existing fusion precedent: native Windows UI Automation controls are augmented with OmniParser detections and passed to an agent in a unified representation. The paper describes discarding visual detections that overlap UIA controls above a 10% IoU threshold. This is useful evidence that hybrid fusion is practical, but such a rule can conflate a container with a nested control; richer semantic alignment is worth testing.

Source: [hybrid control detection, section 3.4](https://arxiv.org/html/2504.14603v2).

### AutoGUI and AutoGUI-v2 — 2025–2026

AutoGUI uses before/after accessibility changes to generate descriptions of element functionality. AutoGUI-v2 adds hierarchical functional regions and tests whether models distinguish similar-looking elements with different functions. Its repository includes region annotation, quality checking, and manual bounding-box correction tools. This is particularly relevant to “rich context”: knowing that an arrow belongs to tab navigation changes its interpretation.

The paper and repository do not make model-generated functional descriptions guaranteed truth. Their annotation pipeline is a starting point for reviewed supervision.

Sources: [AutoGUI paper](https://arxiv.org/abs/2502.01977), [AutoGUI implementation](https://github.com/ZJULiHongxin/AutoGUI), [v2 paper](https://arxiv.org/abs/2604.24441), [v2 tools](https://github.com/ZJULiHongxin/AutoGUI-v2).

## 3. Related work that solves useful pieces

| Work | Contribution relevant here | Boundary |
|---|---|---|
| [ScreenAI](https://arxiv.org/abs/2402.04615) | Screen annotation and UI question answering; [released annotations](https://github.com/google-research-datasets/screen_annotation) | Research/data availability does not imply a downloadable model checkpoint |
| [UIBert](https://arxiv.org/abs/2107.13731) | Joint visual/text UI representations | Mostly mobile representation learning, not temporal desktop state |
| [Screen2Words data](https://github.com/google-research-datasets/screen2words) | 112,085 summaries for 22,417 mobile screens | Summary supervision can omit exact controls and values |
| [UGround](https://osu-nlp-group.github.io/UGround/) | Large-scale instruction-to-element grounding | Finding one target is not a complete parse |
| [GUI-Actor](https://github.com/microsoft/GUI-Actor) | Attention-based target regions plus a grounding verifier | Its verifier evaluates proposed target regions, not whether an executed action succeeded |
| [ShowUI](https://github.com/showlab/ShowUI) | Compact GUI models and public LoRA/QLoRA training support | Primarily grounding/navigation; would need a new output target for our state model |

These works are useful baselines or training recipes. A screen-understanding system should not silently adopt action-prediction quality as its perception metric.

## 4. Temporal understanding and observable changes

### GUI-World — 2024/2025

The dataset includes over 12,000 GUI videos and questions about sequential/dynamic content across multiple environments. It provides a useful temporal-understanding reference. Video QA alone does not give us exact cross-frame element identities or trustworthy action-effect labels.

Sources: [paper](https://arxiv.org/abs/2406.10819), [project/data](https://gui-world.github.io/).

### UI-JEPA — 2024/2025

Apple's work learns UI video representations using self-supervision and a language decoder for user-intent descriptions. It supports the idea that useful temporal representations need not regenerate every pixel. Its task is intent understanding from interaction sequences, not reconstruction of a complete executable screen graph.

Sources: [Apple research](https://machinelearning.apple.com/research/ui-intent), [paper](https://arxiv.org/abs/2409.04081).

### VeriGUI / Don't Act Blindly — 2026

This is directly relevant to repeated ineffective actions. It predicts expected effects, verifies outcomes on the next observation, and trains recovery with synthetic failures and reinforcement learning. The evaluation is based on AndroidControl. It supplies an action-verification formulation, not a reproduced macOS solution.

Source: [paper](https://arxiv.org/abs/2604.05477).

### Beyond Pixel Diffs / WUICC — July 2026

This work studies descriptions of changes between web UI images for visual regression testing. It distinguishes semantic changes from rendering noise. That is useful for our difference descriptions, while its release-comparison setting differs from live interaction: an agent must also handle scrolling, focus, loading, animation, and occlusion.

Source: [paper](https://arxiv.org/abs/2607.01728).

### GUITAR — September 2026

This recent state-transition diagnostic framework groups screens into functional states to locate agent failure bottlenecks. The reported scope is mobile/web tasks. It suggests evaluating failure concentration by state, rather than treating every screenshot as unrelated. It should be treated as recent research, not broad production validation.

Source: [paper](https://arxiv.org/abs/2609.34113).

### CUA-Suite / VideoCUA — 2026

VideoCUA provides roughly 55 hours of professional desktop demonstrations across 87 applications, with continuous recordings and cursor/action information. It is a stronger source for temporal desktop supervision than unrelated natural videos. Demonstrations still require conversion and review to yield element correspondences and semantic event labels.

Sources: [paper](https://arxiv.org/abs/2603.24440), [project](https://cua-suite.github.io/).

## 5. What remains open enough to build

The literature establishes separate pieces. Combining screenshots and AX is not a novel claim by itself, nor is hierarchical screenshot parsing. My synthesis is that a useful project opportunity remains in a measured integration of:

- Native metadata and visual evidence reconciled per field, with conflicts preserved.
- Functional region structure linked to exact underlying elements.
- Temporal identity that survives movement, scrolling, and changing labels where evidence permits.
- Semantic changes separated from cosmetic changes and viewport movement.
- Action-effect evidence with uncertainty and bounded observation requests.
- Detailed internal coverage with concise, queryable external views.

This is an engineering/research direction, not a claim of worldwide novelty. A formal novelty or patent review is outside this survey.

The hard problems are alignment, incomplete observations, and data quality. A VLM can describe a screen plausibly while missing important elements. A raw AX tree can contain exact values while misrepresenting visibility. Fusion must measure disagreement rather than merely concatenate both inputs.

## 6. Proposed representation

Use an internal graph with a primary region hierarchy. It should contain:

**Observation record:** timestamps, app/window identity, screenshot dimensions, coordinate transform, AX capture status, known truncation, visible viewport, and capture skew.

**Element record:** persistent hypothesis ID, current raw references, bounds, text/value, type, raw role, supported actions, state flags, observed visibility, inferred functionality, and provenance/confidence per field.

**Relations:** contains, labels, belongs-to-row/card, controls, aligned-with, obscures, and same-entity-as-previous. Begin with a small set whose annotations can be evaluated.

**Functional regions:** navigation, search results, document canvas, editor, composer, toolbar, modal, and unknown region. Region names are interpretations with evidence, not replacements for the raw source.

**Temporal events:** appeared, disappeared-from-view, moved, value-changed, selected, focus-changed, overlay-opened, loading-started/stopped, and no-relevant-change-observed.

**Effect record:** prior action if supplied, expected observable effect, supporting changes, contradictory evidence, unresolved uncertainty, and observation timeout. A transition after an action is not by itself proof of causation or task completion.

“Not visible now” must remain distinct from “deleted.” “No change observed” must remain distinct from “action failed.” A spinner can stop without a save having succeeded.

A proposed example is:

```text
Window: document editor
Active region: rename dialog
Underlying document: Budget
Name field: focused, value="Budget Q4"
Confirm button: enabled, native action available

Since last observation:
  Rename dialog appeared.
  Focus moved from document canvas to name field.
  Underlying toolbar is visually covered by the dialog.

Prior action: open rename dialog
Expected effect: rename field becomes available
Assessment: expected visible effect observed
Unknown: whether a new name has been committed
```

This output describes evidence and relationships without requiring a planner to reconstruct them from anonymous groups.

## 7. Architecture worth testing

1. **Capture:** screenshot plus AX, with timing and coordinate normalization. Browser DOM is an optional source rather than a prerequisite.
2. **Cheap normalization:** drop proven redundant wrappers, retain source mappings, normalize roles, and preserve native states and values.
3. **Visual completion:** detector and OCR identify missing text/controls; a learned parser proposes structure where AX is poor.
4. **Alignment:** combine location, text, type compatibility, ancestry, and visual context. Support unmatched observations and one-to-many relations.
5. **Semantic enrichment:** a compact model classifies regions and predicts selected relations/functions. Use crops with global context for ambiguous controls.
6. **Tracking:** match elements across observations and estimate viewport transforms. Avoid identifying list rows solely by screen coordinates.
7. **Change interpretation:** compare graph attributes, AX events when available, and visual differences. Use multiple observations for loading and delayed effects.
8. **Query interface:** overview, inspect region, locate by description, changes-since, and expected-effect evidence.

A full parse on every frame is unlikely to be the best latency strategy. An initial parse followed by changed-region updates is a hypothesis to measure. Small changed areas can still be important, so update policy cannot depend on changed pixel area alone.

## 8. Data we can use

| Resource | Intended role | Important limitation |
|---|---|---|
| [Screen2AX suite](https://github.com/MacPaw/Screen2AX) | Native macOS hierarchy/element/group supervision | Annotation quality and limited surface diversity |
| [ScreenParse](https://huggingface.co/datasets/docling-project/screenparse) | Dense web parsing pretraining/adaptation | Native desktop domain gap; pin v1/v2 |
| [GroundCUA](https://github.com/ServiceNow/GroundCUA) | Human-annotated desktop element data: 56K screenshots, 3.56M annotations | Dense boxes do not automatically supply functional edges or temporal labels |
| [VideoCUA](https://cua-suite.github.io/) | Temporal desktop examples | Needs derived/reviewed event and identity labels |
| [AutoGUI-v2](https://github.com/ZJULiHongxin/AutoGUI-v2) | Functional region and difficult semantic evaluation | Generated descriptions need review; some releases remain TODO |
| [Screen Annotation](https://github.com/google-research-datasets/screen_annotation) | UI types, text, and descriptions | Mobile screenshots; not our target distribution |
| Existing Ax_analysis | Capture quirks, native metadata, initial fixtures | Mostly isolated surfaces; not a complete aligned temporal dataset |

Our most valuable new data would be paired, synchronized screenshot/AX sequences with reviewed correspondences and effects. Build that deliberately instead of collecting a large unreviewed pile of screenshots.

Proposed initial scope: 100–200 reviewed screens and 100–200 transitions from 4–6 target applications. This is an evaluation/annotation pilot, not sufficient evidence for broad generalization. Expand based on learning curves and measured error types.

Useful hard examples include duplicate labels, identical icons in different regions, modal occlusion, virtualized lists, scrolling, delayed loading, empty/error states, and deliberately failed actions. Controlled sandbox pages can provide exact state labels; real apps are still needed to measure transfer.

Split evaluation by application, workflow, and session. Adjacent video frames must not leak across training and test partitions. Deduplicate near-identical screens. Keep human-reviewed test labels separate from teacher-generated training labels.

## 9. What 40 GB VRAM changes

Assume one NVIDIA GPU with approximately 40 GB usable VRAM until clarified. These are feasibility estimates, not measured configurations.

| Training target | Assessment | Reason |
|---|---|---|
| UI detector adaptation | Strong starting option | Compact output, existing supervised data, localization-specific loss |
| Small graph/relation/state head over frozen features | Strong starting option | Trainable part can be small; exact values can remain copied from observations |
| Adapt a ~316M parser | Plausible | Fine-tuning a released checkpoint differs greatly from repeating original pretraining |
| 2B–4B multimodal LoRA/QLoRA | Plausible preferred VLM experiment | More room for useful image resolution and before/after pairs |
| 7B–9B multimodal QLoRA | Plausible with constraints | Fit depends heavily on image tokens, sequence length, activations, and trainable modules |
| Full 7B–9B Adam fine-tuning | Poor single-40GB default | Weights, gradients, optimizer state, and activations exceed a simple weight-only budget |
| Large general VLM from scratch | Outside this resource/deadline scope | Data and compute requirements exceed adaptation experiments |

Candidate general models include [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B) and [Qwen3-VL-4B/8B family](https://github.com/QwenLM/Qwen3-VL). Choose via our benchmark and training support rather than assumed recency superiority. [Qwen's training instructions](https://github.com/QwenLM/Qwen3-VL/blob/main/qwen-vl-finetune/README.md) expose component tuning and LoRA; [TRL PEFT](https://huggingface.co/docs/trl/v0.26.0/en/peft_integration) and [memory guidance](https://huggingface.co/docs/trl/reducing_memory_usage) document the relevant techniques.

For intuition, 8B parameters occupy about 16 GB at two bytes each before activation/KV overhead. Four-bit storage reduces the theoretical parameter payload, but metadata and unquantized modules add overhead. Neither calculation is a training-fit guarantee. High-resolution frames and long generated trees can dominate practical memory and latency.

A first VLM configuration to profile would use frozen vision weights, LoRA on supported language/projection modules, microbatch one, gradient accumulation, checkpointing, bounded image tokens, and short structured outputs. Verify that the selected model/trainer actually supports each option. Measure peak allocated/reserved VRAM on real examples before committing to a run.

Do not estimate training time from VRAM. GPU generation, bandwidth, resolution, data size, and target sequence length matter. Multiple GPUs do not automatically pool their memory without a distributed strategy.

## 10. What to train first

Recommended order is empirical, not mandatory:

**A. Evaluate released models without training.** Compare AX-only, image-only, simple AX+OCR fusion, a released dense parser, and a stronger multimodal reference on the same reviewed screens.

**B. Train the weakest valuable component.** If elements are missed, adapt detection. If groups are wrong, train region/relation prediction. If the screen is understood but loops persist, train effect classification/change description.

**C. Use targeted supervision.** Inputs can contain region crops, neighboring element metadata, and before/after observations. Outputs should identify regions, relations, event types, and evidence references. Avoid teaching the model to rewrite exact field values already available from AX.

**D. Distill only reviewed behavior.** Strong teachers can propose annotations, but examples should carry provenance, review status, and disagreement. Syntactically valid JSON is not proof of correct perception.

Possible learning objectives are element localization/type classification, parent/relationship prediction, region-function classification, cross-frame matching, state-change classification, and expected-effect entailment. A graph neural network is optional; a small classifier or transformer over candidate pairs may be enough. Establish simple baselines first.

## 11. Evaluation that would make this convincing

| Capability | Proposed evidence |
|---|---|
| Coverage | Precision/recall of visible elements and text; explicit missing regions |
| Structure | Parent/relationship F1 and region overlap, allowing equivalent valid grouping |
| Semantics | Region/function questions and difficult duplicate-control distinctions |
| State | Per-attribute precision/recall, especially disabled/selected/focused/covered |
| Continuity | Match accuracy, ID switches, and scroll-vs-removal classification |
| Change | Event precision/recall and no-change false positives |
| Effect | Expected-effect accuracy with uncertain cases and false-success rate |
| Efficiency | Warm/cold p50/p95 latency, output tokens, peak memory, per-screen cost |
| Downstream usefulness | Fixed decision model; compare its accuracy and repeated ineffective actions across representations |

Public evaluation anchors: [UI-Vision](https://github.com/uivision/UI-Vision) for desktop layout/element questions, [OSWorld-G](https://github.com/xlang-ai/OSWorld-G) for layout and manipulation grounding, and AutoGUI-v2 for functionality. These complement a custom temporal benchmark; none alone measures the complete proposed service.

Hold the downstream decision model and prompts as constant as feasible across ablations. If a larger model, more history, or extra calls are introduced, report that separately from representation improvements. A confidence score should be calibrated on held-out data, with accuracy reported at different abstention/coverage levels.

## 12. A one-week proof of concept

This is a suggested sequence, not a promise of training throughput:

- **Day 1:** finalize the state/event schema and reviewed pilot benchmark; synchronize capture.
- **Day 2:** reproduce AX-only, screenshot-only, and simple fusion baselines.
- **Day 3:** compare Screen2AX, ScreenParser/ScreenVLM, and a general VLM on target screens.
- **Day 4:** implement or improve matching, region structure, identity, and observable changes.
- **Day 5:** run one narrowly justified training experiment if data and baseline errors support it.
- **Day 6:** evaluate unseen sessions/apps, failure cases, and latency; retain the best baseline if training fails to help.
- **Day 7:** prepare a demonstrator showing raw inputs, structured interpretation, temporal events, uncertainty, and comparative results.

The strongest demo would let a person click a region of a real screen and inspect its elements, relationships, sources, and changes. Demonstrate failed clicks, scrolling, and modal overlays as well as successful transitions. A compact model with measured improvement is more credible than a broad claim of complete UI understanding.

## 13. Practical cautions specific to adoption

Record exact dataset and checkpoint revisions. Paper results and current model cards may describe different releases. Public release claims are not installation tests.

The Screen2AX repository describes different licenses for code, datasets, and detector weights. Some detector tooling also has separate terms. The ScreenVLM card lists Apache-2.0. Check the exact artifacts selected before embedding them in a distributed product; this review is not a license audit. [Screen2AX component terms](https://github.com/MacPaw/Screen2AX), [ScreenVLM card](https://huggingface.co/docling-project/ScreenVLM).

Use synthetic or consented capture content for annotation. Preserve exact text only where needed, with separate redaction for shared training material. Screen data can include credentials and private documents.

## Recommendation

Build the first version around **native AX evidence + visual completion + functional regions + temporal matching and semantic events**. Treat a compact parser and a small effect/relation model as the leading trainable components. Keep the exact model choice open until the same reviewed benchmark exposes where existing tools fail.

The technical claim worth pursuing is that this representation improves understanding and change recognition at a measured cost. It should be demonstrated independently of a full desktop assistant.
