"""
LangGraph state schema for LLM OS Harness.
"""
import os
from typing import TypedDict, Any, List, Dict, Optional


class HarnessState(TypedDict):
    task: str                          # The user's natural language instruction
    platform: str                      # 'macos' (extensible later)
    messages: List[Dict[str, Any]]     # Full LLM conversation history (OpenAI messages format)
    current_tree: Dict[str, Any]       # Latest full DFS AX tree snapshot
    previous_tree: Dict[str, Any]      # Previous step's tree (for diffing), can be empty dict
    state_diff: str                    # Git-style unified diff string
    step_count: int                    # Current step number
    max_steps: int                     # Budget (default: 20)
    status: str                        # 'running' | 'done' | 'failed' | 'awaiting_user'
    pending_question: str              # Disambiguation question for the user (empty string if none)
    pending_options: List[str]         # Options for disambiguation (empty list if none)
    learnings: str                     # Contents of learnings.md (loaded once at start)
    execution_log_path: str            # Path to the .diff.log file
    last_tool_result: Dict[str, Any]   # Result from the last tool execution
    _pending_tool_call: Dict[str, Any] # Tool call returned by reason
    _app_hint: Optional[str]           # Target application hint
    _pending_tool_call: Optional[Dict[str, Any]] # Pending tool call to execute
    _app_hint: Optional[str]           # Hint for target app


def create_initial_state(
    task: str,
    log_path: str,
    learnings_path: Optional[str] = None,
    platform: str = 'macos',
    max_steps: int = 20
) -> HarnessState:
    """
    Initializes the harness state with sensible defaults.
    
    Args:
        task: The user's natural language instruction.
        log_path: Path to the .diff.log file.
        learnings_path: Optional path to a learnings.md file to load.
        platform: Platform string (default 'macos').
        max_steps: Maximum step budget.
        
    Returns:
        HarnessState: The initialized state dictionary.
    """
    learnings = ""
    if learnings_path and os.path.exists(learnings_path):
        try:
            with open(learnings_path, 'r', encoding='utf-8') as f:
                learnings = f.read()
        except Exception as e:
            # Silently fallback to empty string on error
            pass

    return {
        "task": task,
        "platform": platform,
        "messages": [],
        "current_tree": {},
        "previous_tree": {},
        "state_diff": "",
        "step_count": 0,
        "max_steps": max_steps,
        "status": "running",
        "pending_question": "",
        "pending_options": [],
        "learnings": learnings,
        "execution_log_path": log_path,
        "last_tool_result": {},
        "_pending_tool_call": {},
        "_app_hint": None
    }
