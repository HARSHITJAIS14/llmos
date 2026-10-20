# Pilot Report: macOS Contextual Screen-Perception Dataset (v0.1.0)

**Date**: 2026-10-18  
**Workspace**: `/Users/harshit/Desktop/YC`  
**Dataset Path**: `screen_understanding/dataset/pilot_v001/`  
**Review Viewer**: `screen_understanding/dataset/pilot_v001/review/index.html`  
**Detector**: OmniParser-v2.0-icon_detect on remote `gpu3` (checkpoint `dab3d4351ad0...`, NVIDIA A40)  
**Total Screens**: 30 genuine macOS native screencaptures (0% synthetic / 0% PIL generated)  
**Total Ground Truth DAG Nodes**: 342  
**Total Proposals Resolved**: 1,235 (100% coverage disposition mapping)  
**Total Temporal Pairs**: 5 before/after state transition pairs  
**Validation Pass Rate**: 100% (30/30 screens and 5/5 pairs valid against strict schemas)

---

## 1. Executive Summary

In full accordance with [GEMINI_DATASET_PLAN.md](file:///Users/harshit/Desktop/YC/screen_understanding/dataset/GEMINI_DATASET_PLAN.md) and strict user mandates, we have completed the **30-screen pilot dataset** across **6 distinct strata** on real native macOS applications.

### Core Directives Enforced:
1. **Strictly Real Screenshots Across System**: Every single screen was captured directly from live macOS windows via native `screencapture -x -o -l<wid>`, covering native applications including Safari, Google Chrome, Finder, macOS Desktop, Visual Studio Code, macOS Terminal, TextEdit, System Settings, native File Dialogs, Preview, Apple Numbers, Apple Podcasts, Weather, Calculator, Calendar, and App Store. All synthetic / Pillow-mocked images were permanently discarded.
2. **GPU Proposal Detection**: All candidate proposal bounding boxes were detected using the OmniParser-v2.0 icon detector on remote cluster GPU (`gpu3`, NVIDIA A40), achieving median detector inference latency of ~58ms per screen.
3. **DAG Ground Truth & Strict Hierarchy**: Every screen was visually inspected, annotated into a single-root directed acyclic graph (`n_0000`), with coordinate bounds matching source pixel spaces, strict schema role enums, and comprehensive text and state ground truth.
4. **100% Proposal Disposition Mapping**: All 1,235 raw detector proposals are fully accounted for with valid dispositions (`retained`, `merged`, `suppressed`) mapped to ground truth node IDs. Zero unresolved proposals remain.
5. **Temporal Pairs**: Exactly 5 before/after state transition pairs (`pair_01` to `pair_05`) were captured and tracked with node-level correspondence across navigation, selection, command execution, and pagination.

---

## 2. Pilot Dataset Strata Breakdown

| Stratum | Screens | Temporal Pair | Apps Represented | Total Nodes | Total Proposals |
| :--- | :---: | :---: | :--- | :---: | :---: |
| **1. Browser interface and web content** | `mac_0001`, `0004`, `0005`, `0006`, `0007` (5) | `pair_01` (`0006` -> `0007`) | Safari, Google Chrome | 59 | 293 |
| **2. Finder and desktop** | `mac_0002`, `0008`, `0009`, `0010`, `0011` (5) | `pair_02` (`0010` -> `0011`) | Finder, macOS Desktop | 59 | 212 |
| **3. Editor and terminal** | `mac_0012`, `0013`, `0014`, `0015`, `0016` (5) | `pair_03` (`0015` -> `0016`) | VS Code, Terminal, TextEdit | 46 | 96 |
| **4. Settings, forms and dialogs** | `mac_0003`, `0017`, `0018`, `0019`, `0020` (5) | `pair_04` (`0019` -> `0020`) | System Settings, File Dialog | 74 | 211 |
| **5. Documents, PDFs and tables** | `mac_0021`, `0022`, `0023`, `0024`, `0025` (5) | `pair_05` (`0024` -> `0025`) | Preview, Apple Numbers | 44 | 302 |
| **6. Communication and media** | `mac_0026`, `0027`, `0028`, `0029`, `0030` (5) | Independent screens | App Store, Weather, Calculator, Calendar, Podcasts | 60 | 121 |
| **TOTAL** | **30 Screens** | **5 Pairs** | **15 Native Mac Apps** | **342 Nodes** | **1,235 Proposals** |

---

## 3. Temporal State-Transition Pairs

All five required before/after pairs were captured from live application state transitions, validated against `pair.schema.json`:

1. **`pair_01` (Browser interface & web content)**:
   - `before`: `mac_0006` (GitHub repository Code tab)
   - `after`: `mac_0007` (GitHub repository Pull requests tab)
   - *Changes*: Tab underline switched (`state_changed`), repository file tree replaced by pull requests listing table (`text_changed`).
2. **`pair_02` (Finder and desktop)**:
   - `before`: `mac_0010` (Finder Utilities list, unselected state)
   - `after`: `mac_0011` (Finder Utilities list, Terminal.app row selected)
   - *Changes*: Row selection highlight appeared (`state_changed`), Terminal metadata card opened in inspector (`appeared`).
3. **`pair_03` (Editor and terminal)**:
   - `before`: `mac_0015` (Terminal with command staged at prompt)
   - `after`: `mac_0016` (Terminal after running `git status -s` command)
   - *Changes*: Command output error displayed (`appeared`), interactive shell prompt repositioned (`moved`).
4. **`pair_04` (Settings, forms and dialogs)**:
   - `before`: `mac_0019` (System Settings Bluetooth category selected)
   - `after`: `mac_0020` (System Settings Sound category selected)
   - *Changes*: Category sidebar selection transitioned (`state_changed`), content pane replaced with sound alert and output controls (`text_changed`).
5. **`pair_05` (Documents, PDFs and tables)**:
   - `before`: `mac_0024` (Preview viewing Page 1 of multi-page PDF)
   - `after`: `mac_0025` (Preview viewing Page 2 following pagination scroll)
   - *Changes*: Page 1 abstract and figure scrolled out, Page 2 Overview section entered viewport (`text_changed`).

---

## 4. Pipeline & Validation Integrity

Every screen directory contains:
- `source.png`: The original, lossless full-resolution PNG screencapture.
- `source_metadata.json`: SHA-256 hash, native dimensions, scale factor (2.0 Retina), stratum, app family, and appearance.
- `proposals/raw.json`: Candidate proposal bounding boxes output directly by the remote YOLO detector on `gpu3`.
- `proposals/candidates.json`: Processed candidate boxes formatted for the pipeline.
- `annotation.teacher.json`: Complete teacher ground-truth DAG.
- `annotation.reviewed.json`: Verified, audit-applied ground truth DAG matching `annotation.schema.json`.
- `audit_overlay.png`: High-resolution visual overlay with color-coded bounding boxes and semantic node labels.
- `validation.json`: Detailed validation certificate verifying schema compliance, single-root DAG structure, coordinate constraints, and proposal coverage.

### Validation Status:
- **Screens Validated**: 30 / 30 (100% Passed)
- **Pairs Validated**: 5 / 5 (100% Passed)
- **Coordinate Space**: 100% `source_pixels_xyxy` conforming to source dimensions
- **Unresolved Proposals**: 0 across all 30 screens

---

## 5. Dataset Splits & Manifest

- **`manifest.jsonl`**: Complete 30-entry catalog with hashes, geometry, stratum, and proposal counts.
- **`splits.json`**:
  - `train`: 20 screens (`mac_0001`, `0002`, `0004`, `0005`, `0006`, `0007`, `0008`, `0009`, `0010`, `0011`, `0012`, `0013`, `0014`, `0015`, `0016`, `0026`, `0027`, `0028`, `0029`, `0030`)
  - `val`: 5 screens (`mac_0003`, `0017`, `0018`, `0019`, `0020`)
  - `test`: 5 screens (`mac_0021`, `0022`, `0023`, `0024`, `0025`)
- All before/after pairs are strictly preserved within the same split to avoid data leakage.

---

## 6. Review Tool Access

To inspect any screen, bounding box overlays, proposal dispositions, and temporal tracks interactively:
Open [screen_understanding/dataset/pilot_v001/review/index.html](file:///Users/harshit/Desktop/YC/screen_understanding/dataset/pilot_v001/review/index.html) in any browser.

The pilot dataset is completely assembled, verified, and ready for production expansion.
