# **LLMOS: Project Blueprint & Startup Vision**

**Project Name:** Next Big Thing (Working Title) / LLMOS

**Core Mission:** To build an OS-level AI assistant that executes multi-step workflows faster than a human can using a mouse and keyboard.

## **1. Executive Summary**

LLMOS (Large Language Model Operating System) is an Agentic AI layer that sits directly on top of the user's operating system. Instead of merely generating text, LLMOS translates natural language (specifically voice commands, leveraging models like Whisper) into executable actions. The ultimate goal is to create a frictionless, hands-free computing experience where users can queue up tasks asynchronously while focusing on deep work.

## **2. The "Aha!" Moment: Restricting the Use Case**

The AI graveyard is full of startups that promised to do everything and delivered nothing. LLMOS differentiates itself by strictly avoiding vague, open-ended commands and focusing intensely on specific, highly-structured daily workflows.

- **The Anti-Goal (Vague/Impossible):** *"Build me Facebook."* (Too broad, sets false expectations).
- **The Sweet Spot (Developer Workflow):** *"Create a repo named 'Next Big Thing' and create a local copy in the Projects folder."*
- **The Sweet Spot (Productivity Workflow):** *"Open Notion, go to My Day template and add Chest day."*

## **3. Technical Architecture & Strategy**

To achieve the necessary speed and reliability, the system architecture must bypass traditional, fragile automation methods.

| Approach | Mechanism | Drawbacks | LLMOS Verdict |
| --- | --- | --- | --- |
| **API Integrations** | Connecting directly to app backends (e.g., Notion API, GitHub API). | Not every company provides an API. Relying on third-party APIs makes the business unsustainable and vulnerable to rate limits or revocations. | **Discard as Primary** |
| **Pure Computer Vision (CV)** | Taking screenshots, running OCR, object detection, calculating coordinates, and simulating clicks. | Incredibly slow (5-10 seconds per action). Breaks easily if an app updates its UI or changes background colors. Compute-heavy. | **Use as Fallback Only** |
| **Accessibility Tree (The Secret Sauce)** | Querying the OS-level UI tree (designed for screen readers) to get a structured JSON/XML map of all active windows, buttons, and text fields. | Requires apps to be built with proper accessibility tags (can struggle with some poorly-built web wrappers like certain Electron apps). | **Primary Execution Engine** |

### **The Hybrid Execution Model**

LLMOS will primarily utilize the **OS Accessibility Tree**. This allows the AI to instantly parse the screen's DOM, calculate exact coordinates in milliseconds, and execute clicks/typing programmatically. For the minority of applications where developers have failed to implement proper accessibility tags (the "leftovers"), LLMOS will seamlessly fall back to a highly-optimized **Computer Vision/Screenshot** pipeline to bridge the gap.

// LLMOS Decision Pipeline

Command Received -> Parse Intent

If Element in Accessibility Tree:

Execute via OS GUI Tree (Latency: < 0.5s)

Else:

Capture Screenshot -> Locate Element -> Execute (Latency: ~2-3s)

## **4. Key Performance Indicators (KPIs) & User Experience**

- **North Star Metric: Time-to-Execution.** The total time from voice command to action completion MUST be faster than a user executing the same task manually with a mouse and keyboard.
- **Asynchronous Queuing:** Users should be able to rattle off multiple requests (e.g., "Draft an email to John, then open my calendar and block off 3 PM") and have LLMOS queue and execute them in the background without freezing the user's workflow.

## **5. Next Steps for MVP**

1. Define the target operating system for V1 (macOS vs. Windows).
2. Build the parser for the Accessibility Tree on the chosen OS.
3. Train the intent-matching engine to map restricted voice commands to the specific GUI nodes.
4. Implement the vision fallback for non-compliant UI elements.

## **6. Ideas & Architectural Experiments**

- **Universal Browser DOM Engine (`utils/universal_browser_dom.py`):**
  - **The Problem:** OS Accessibility (AX) trees treat browsers (Brave, Safari, Chrome, Arc) as opaque desktop windows. OS AX snapshots lack internal DOM context, truncate web subtrees, fail on React/Vue controlled component `onChange` state traps, and suffer from Retina/multi-monitor coordinate offsets.
  - **The Solution:** A universal cross-browser DOM injection engine using native AppleScript / JavaScript bridges (`tell application "<Browser>" to execute front window active tab javascript "..."`).
  - **Why it Matters:** Allows LLM_OS to control web applications (Hotstar, YouTube, Twitter, Google Docs) seamlessly inside **ANY browser** (Safari, Brave, Chrome, Arc, Edge) with direct DOM querying (`document.querySelector`), zero coordinate flakiness, and native React synthetic event dispatching (`input`, `change`, `click`).