# Experiment: Harness State-Diff Workflow Logging

## Overview
This experiment introduces a **Git-style State Diff Logging System** for the LLM_OS Harness.

In complex multi-step workflows, each task is represented as a sequence of `(tree_state, action)` pairs:
$$S_0 \xrightarrow{A_1} S_1 \xrightarrow{A_2} S_2 \dots \xrightarrow{A_n} S_n$$

Instead of dumping full duplicate JSON trees for every single action step, the harness computes git-style unified diffs (`+` additions, `-` deletions, `@@` line breaks) between $S_{t-1}$ and $S_t$. This produces a single, human-comprehensible, highly debuggable workflow execution log (`workflow_execution.diff.log`).

## Key Features

1. **State Normalization (`utils/state_diff.py`)**:
   - Formats JSON tree snapshots into canonical multi-line sorted strings.
   - Optionally strips ephemeral/session-specific snapshot hash prefixes (`@s1faoqstpdf3hc:e1` $\rightarrow$ `:e1`) and `snapshot_id` fields so diffs highlight semantic UI state changes rather than random hash noise.

2. **Unified Git Diffs**:
   - Uses `difflib.unified_diff` to generate standard git diff hunks with configurable line breaks and context lines (`@@ -1,14 +1,88 @@`).

3. **Harness Logger (`utils/harness_logger.py`)**:
   - Stateful logger managing `start_workflow`, `log_initial_state`, `log_action`, and `finalize`.
   - Formats steps with action metadata, timestamps, and state diff chunks.

## File Inventory

| File | Description |
|---|---|
| `utils/state_diff.py` | State tree canonical normalization & git-style unified diff generation module |
| `utils/harness_logger.py` | Stateful Harness Logger tracking workflow step sequences and logging state diffs |
| `test_state_diff.py` | Unit tests for normalization, git diff generation, and `HarnessLogger` |
| `run_task_with_diff.py` | Live multi-step task execution script demonstrating state-diff logging on macOS Calendar |
| `workflow_execution.diff.log` | Sample generated execution log displaying git diffs across all workflow steps |

## How to Run

### 1. Run Unit Tests
```bash
python3 experiments/state_diff_harness/test_state_diff.py
```

### 2. Run Workflow Task with Live State Diff Logging
```bash
python3 experiments/state_diff_harness/run_task_with_diff.py "Sync meeting at 5 pm"
```

### 3. Inspect Log File
```bash
cat experiments/state_diff_harness/workflow_execution.diff.log
```
