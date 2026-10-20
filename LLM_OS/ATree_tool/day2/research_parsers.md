# macOS Accessibility Tree Parsers: A Deep Dive Research

## Overview
This document explores the landscape of macOS accessibility tree parsers and GUI automation frameworks. Currently, our system utilizes `agent-desktop`, but exploring alternatives like `GUIrilla` and others is crucial for optimizing latency, reducing token usage, and improving stability.

## 1. Data-Crawling & Research Frameworks

### **GUIrilla (by MacPaw)**
- **GitHub:** [MacPaw/GUIrilla](https://github.com/MacPaw/GUIrilla) & [MacPaw/macapptree](https://github.com/MacPaw/macapptree)
- **Description:** A scalable framework designed specifically for automated exploration of macOS GUIs to train foundation models and GUI agents. It is not an autonomous agent itself but a data-crawling framework.
- **Key Features:** 
  - Extracts the accessibility tree into hierarchical "MacApp Trees".
  - Captures screenshots with labeled bounding boxes.
  - Used to generate large datasets like `GUIrilla-Task` (27k tasks across 1k apps).
  - Released alongside foundation models (`GUIrilla-See`).
- **Use Case for LLMOS:** Excellent reference for how to structure Accessibility API data for LLMs and how to handle bounding box extraction. If we ever need to fine-tune our Computer Vision fallback, `macapptree` is the perfect tool for generating training data.

## 2. Agent-Centric UI Parsers (LLM-Optimized)

### **macos-use (by mediar-ai)**
- **GitHub:** [mediar-ai/mcp-server-macos-use](https://github.com/mediar-ai/mcp-server-macos-use) & [mediar-ai/MacosUseSDK](https://github.com/mediar-ai/MacosUseSDK)
- **Description:** An advanced project built specifically for AI agents, functioning as an MCP (Model Context Protocol) server.
- **Key Features:**
  - **The "Diff" Approach:** Instead of feeding the entire UI tree to the LLM every time (which wastes tokens and time), it provides "diffs" after an action (e.g., clicking or typing).
  - **Noise Reduction:** Filters out noise like scrollbars or empty containers to provide a compact, actionable representation.
- **Use Case for LLMOS:** Highly relevant. The "diff" approach is a critical optimization for our goal of executing multi-step workflows faster than a human.

### **py2mac**
- **GitHub:** [raphaelwio/py2mac](https://github.com/raphaelwio/py2mac)
- **Description:** A Python interface enabling autonomous AI agents to interact with macOS via the accessibility tree.
- **Key Features:** Includes data cleaning tools specifically designed to format UI trees for LLM frameworks like LangChain.

## 3. General Automation & Testing Libraries (Wrapper Libraries)

### **atomacos**
- **GitHub:** [OpenAdaptAI/atomacos](https://github.com/OpenAdaptAI/atomacos)
- **Description:** A Python library (forked from `atomac`) that provides direct access to the Apple Accessibility API via `pyobjc`.
- **Key Features:** Clean object-oriented interface for traversing the UI hierarchy. Very popular for standard Python-based GUI testing.

### **xa11y**
- **GitHub:** [crowecawcaw/xa11y](https://github.com/crowecawcaw/xa11y)
- **Description:** A cross-platform Rust library with Python/JS bindings.
- **Key Features:** Provides a Playwright-style API for driving desktop applications through accessibility trees.

### **AXorcist**
- **GitHub:** [eiz/AXorcist](https://github.com/eiz/AXorcist)
- **Description:** A Swift wrapper for the macOS Accessibility API.
- **Key Features:** Provides a type-safe, chainable API. Best if we decide to build native Swift components instead of relying on Rust or Python.

### **axuielement (Rust)**
- **GitHub:** [axuielement](https://crates.io/crates/axuielement)
- **Description:** Safe Rust bindings for the macOS Accessibility API.
- **Key Features:** Ideal for high-performance, type-safe interactions. Supports asynchronous observers for monitoring UI changes. (Similar to what `agent-desktop` likely uses under the hood).

## 4. Key Takeaways & Recommendations for LLMOS

1. **Adopt the "Diff" Strategy:** The approach used by `macos-use` (sending only state changes/diffs to the LLM) is a major optimization. We should investigate implementing this pattern on top of `agent-desktop` or migrating to `macos-use` if it offers lower latency.
2. **Aggressive Noise Reduction:** `GUIrilla` and `macos-use` both emphasize filtering out non-actionable elements (scrollbars, hidden containers). Our parser must aggressively prune the accessibility tree before passing it to the intent-matching engine to maintain speed.
3. **Data Collection for Vision Fallback:** If we need to fine-tune our own models for the Computer Vision fallback (when Accessibility Trees fail), `GUIrilla`'s `macapptree` library is the perfect tool for collecting labeled screenshot data.
4. **Underlying Technology:** All these tools rely on the same underlying Apple `AXUIElement` API. They all require strict Accessibility permissions and generally cannot run in sandboxed environments, which aligns with our current architecture constraints.
