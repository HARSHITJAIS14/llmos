"""
LLM_OS Orchestrator — LangGraph Cognitive Loop.

Implements the Perceive → Diff → Reason → Execute → Loop state machine
as a LangGraph StateGraph. This is the central brain of the harness.
"""
import json
import logging
import os
import sys
import time
import datetime
from typing import Any

from langgraph.graph import StateGraph, END
from openai import OpenAI

from llm_os.state import HarnessState
from llm_os.perception import (
    capture_state,
    extract_tree,
    compute_diff,
    summarize_tree_for_llm,
)
from llm_os.aci import TOOL_SCHEMAS, dispatch
from llm_os.prompts import build_system_prompt, load_learnings

# Add ATree_tool to path for HarnessLogger
_ATREE_ROOT = os.path.join(os.path.dirname(__file__), '..', 'ATree_tool')
if _ATREE_ROOT not in sys.path:
    sys.path.insert(0, os.path.abspath(_ATREE_ROOT))
from utils.harness_logger import HarnessLogger

logger = logging.getLogger('llm_os.orchestrator')


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

def _get_llm_client() -> OpenAI:
    """Create an OpenAI client from environment variables."""
    if os.environ.get('GROQ_API_KEY'):
        return OpenAI(
            api_key=os.environ.get('GROQ_API_KEY'),
            base_url='https://api.groq.com/openai/v1',
        )
    return OpenAI(
        api_key=os.environ.get('OPENAI_API_KEY', ''),
        base_url=os.environ.get('OPENAI_BASE_URL'),
    )


def _get_model() -> str:
    """Get the model name from environment or default."""
    if os.environ.get('ANTHROPIC_API_KEY'):
        return os.environ.get('LLM_OS_MODEL', 'claude-sonnet-5')
    if os.environ.get('GROQ_API_KEY'):
        return os.environ.get('LLM_OS_MODEL', 'llama-3.1-70b-versatile')
    return os.environ.get('LLM_OS_MODEL', 'gpt-4o')


# ---------------------------------------------------------------------------
# Graph Node Functions
# ---------------------------------------------------------------------------

def perceive(state: HarnessState) -> dict:
    """PERCEIVE: Capture current AX tree state.

    - Moves current_tree to previous_tree
    - Captures a fresh full DFS tree
    - Increments step count (except for the initial capture)
    """
    logger.info(f'[Step {state["step_count"]}] PERCEIVE')

    # Determine target app from task context (simple heuristic)
    # The LLM could specify this more precisely via tool args in future
    app_name = _infer_app_name(state)

    # Shift trees
    previous_tree = state.get('current_tree', {})

    # Capture fresh state
    snapshot = capture_state(app_name=app_name)
    current_tree = extract_tree(snapshot)

    return {
        'previous_tree': previous_tree,
        'current_tree': current_tree,
    }


def diff(state: HarnessState) -> dict:
    """DIFF: Generate git-style state diff between previous and current tree.

    Also manages the LLM context window by evicting old tree snapshots
    and keeping only state diffs + current tree summary.
    """
    logger.info(f'[Step {state["step_count"]}] DIFF')

    prev = state.get('previous_tree', {})
    curr = state.get('current_tree', {})

    if prev:
        state_diff = compute_diff(prev, curr)
    else:
        state_diff = '(Initial state capture — no previous state to diff against)'

    # Generate compact tree summary for LLM
    tree_summary = summarize_tree_for_llm(curr, max_depth=2)
    if len(tree_summary) > 1000:
        tree_summary = tree_summary[:1000] + '\n... (tree truncated)'

    # Build the user message with state info
    step = state['step_count']
    last_result = state.get('last_tool_result', {})

    context_parts = []

    if step == 0:
        context_parts.append(f'## Task\n{state["task"]}')
        context_parts.append(f'## Initial AX Tree State (S0)\n```\n{tree_summary}\n```')
    else:
        if last_result:
            context_parts.append(
                f'## Previous Action Result\n'
                f'Status: {last_result.get("status", "unknown")}\n'
                f'Message: {last_result.get("message", "")}'
            )

        # Truncate very long diffs to avoid blowing context
        diff_display = state_diff
        if len(state_diff) > 1000:
            diff_display = state_diff[:1000] + '\n... (diff truncated, showing first 1000 chars)'

        context_parts.append(f'## State Diff (S{step-1} → S{step})\n```diff\n{diff_display}\n```')
        context_parts.append(f'## Current AX Tree State (S{step})\n```\n{tree_summary}\n```')

    user_message = '\n\n'.join(context_parts)

    # Context window management: evict old tree snapshots from messages
    # Keep only the system prompt + last N messages to prevent token explosion
    messages = _manage_context_window(state['messages'], user_message)

    return {
        'state_diff': state_diff,
        'messages': messages,
    }


def reason(state: HarnessState) -> dict:
    """REASON: Send state to LLM, get tool call or terminal signal."""
    # Check step budget
    if state['step_count'] >= state['max_steps']:
        logger.warning(f'Step budget exhausted ({state["max_steps"]})')
        return {
            'status': 'failed',
            'last_tool_result': {
                'status': 'failed',
                'message': f'Step budget exhausted after {state["max_steps"]} steps',
            },
        }

    if os.environ.get('ANTHROPIC_API_KEY'):
        return _reason_anthropic(state)
    else:
        return _reason_openai(state)


def _reason_anthropic(state: HarnessState) -> dict:
    """Anthropic-specific reasoning implementation."""
    import anthropic
    logger.info(f'[Step {state["step_count"]}] REASON (Anthropic)')

    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    model = _get_model()

    # 1. Convert tools
    anthropic_tools = []
    for t in TOOL_SCHEMAS:
        anthropic_tools.append({
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "input_schema": t["function"]["parameters"],
        })
        
    # 2. Convert messages
    system_prompt = ""
    anthropic_messages = []
    
    for msg in state['messages']:
        role = None
        blocks = []
        
        if msg['role'] == 'system':
            if msg.get('content'):
                system_prompt += msg['content'] + "\n"
            continue
        elif msg['role'] == 'user':
            role = 'user'
            if msg.get('content'):
                blocks.append({"type": "text", "text": msg['content']})
        elif msg['role'] == 'assistant':
            role = 'assistant'
            if 'anthropic_blocks' in msg:
                blocks.extend(msg['anthropic_blocks'])
            else:
                if msg.get('content'):
                    blocks.append({"type": "text", "text": msg['content']})
                for tc in msg.get('tool_calls', []):
                    blocks.append({
                        "type": "tool_use",
                        "id": tc['id'],
                        "name": tc['function']['name'],
                        "input": json.loads(tc['function']['arguments'])
                    })
        elif msg['role'] == 'tool':
            role = 'user'
            blocks.append({
                "type": "tool_result",
                "tool_use_id": msg['tool_call_id'],
                "content": msg.get('content', '')
            })
            
        if blocks:
            if anthropic_messages and anthropic_messages[-1]['role'] == role:
                anthropic_messages[-1]['content'].extend(blocks)
            else:
                anthropic_messages.append({"role": role, "content": blocks})

    try:
        response = client.messages.create(
            model=model,
            system=system_prompt.strip() if system_prompt else anthropic.NOT_GIVEN,
            messages=anthropic_messages,
            tools=anthropic_tools,
            max_tokens=1024,
        )
    except Exception as e:
        logger.exception('Anthropic API call failed')
        return {
            'status': 'failed',
            'last_tool_result': {'status': 'error', 'message': f'Anthropic API error: {e}'},
        }

    # Parse response back to OpenAI format for state compatibility
    assistant_msg = {"role": "assistant", "content": ""}
    tool_calls = []
    anthropic_blocks = []
    
    for block in response.content:
        # Convert block to dict for raw preservation (preserves thinking blocks)
        if hasattr(block, 'model_dump'):
            anthropic_blocks.append(block.model_dump())
        elif hasattr(block, 'dict'):
            anthropic_blocks.append(block.dict())
        else:
            anthropic_blocks.append(vars(block))
            
        if block.type == 'text':
            assistant_msg['content'] += block.text
        elif block.type == 'tool_use':
            tool_calls.append({
                'id': block.id,
                'type': 'function',
                'function': {
                    'name': block.name,
                    'arguments': json.dumps(block.input)
                }
            })
            
    if tool_calls:
        assistant_msg['tool_calls'] = tool_calls
    if anthropic_blocks:
        assistant_msg['anthropic_blocks'] = anthropic_blocks

    if assistant_msg['content']:
        logger.info(f'LLM reasoning: {assistant_msg["content"][:500]}')
        print(f'\n🧠 REASONING (Step {state["step_count"]}):\n{assistant_msg["content"]}\n')

    messages = state['messages'].copy()
    messages.append(assistant_msg)

    if not tool_calls:
        logger.warning('LLM responded without a tool call')
        return {
            'messages': messages,
            'last_tool_result': {'status': 'error', 'message': 'No tool call in response'},
        }

    tc = tool_calls[0]
    tool_name = tc['function']['name']
    tool_args = json.loads(tc['function']['arguments'])

    logger.info(f'Tool call: {tool_name}({tool_args})')
    print(f'🔧 TOOL: {tool_name}({json.dumps(tool_args, indent=2)})')

    return {
        'messages': messages,
        '_pending_tool_call': {
            'id': tc['id'],
            'name': tool_name,
            'arguments': tool_args,
        },
    }


def _reason_openai(state: HarnessState) -> dict:
    """OpenAI-compatible reasoning implementation."""
    logger.info(f'[Step {state["step_count"]}] REASON (OpenAI)')

    client = _get_llm_client()
    model = _get_model()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=state['messages'],
            tools=TOOL_SCHEMAS,
            tool_choice='auto',
            temperature=0.0,
        )
    except Exception as e:
        logger.exception('LLM API call failed')
        return {
            'status': 'failed',
            'last_tool_result': {'status': 'error', 'message': f'LLM API error: {e}'},
        }

    message = response.choices[0].message

    # Log the LLM's reasoning
    if message.content:
        logger.info(f'LLM reasoning: {message.content[:500]}')
        print(f'\n🧠 REASONING (Step {state["step_count"]}):\n{message.content}\n')

    # Add assistant message to history
    messages = state['messages'].copy()
    messages.append(_message_to_dict(message))

    if not message.tool_calls:
        # No tool call — the LLM just responded with text
        logger.warning('LLM responded without a tool call')
        return {
            'messages': messages,
            'last_tool_result': {'status': 'error', 'message': 'No tool call in response'},
        }

    # Process the first tool call
    tool_call = message.tool_calls[0]
    tool_name = tool_call.function.name
    try:
        tool_args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError:
        tool_args = {}

    logger.info(f'Tool call: {tool_name}({tool_args})')
    print(f'🔧 TOOL: {tool_name}({json.dumps(tool_args, indent=2)})')

    return {
        'messages': messages,
        '_pending_tool_call': {
            'id': tool_call.id,
            'name': tool_name,
            'arguments': tool_args,
        },
    }


def execute_tool(state: HarnessState) -> dict:
    """EXECUTE: Dispatch the pending tool call and record the result."""
    pending = state.get('_pending_tool_call', {})
    tool_name = pending.get('name', '')
    tool_args = pending.get('arguments', {})
    tool_call_id = pending.get('id', '')

    logger.info(f'[Step {state["step_count"]}] EXECUTE: {tool_name}')

    # Dispatch
    result = dispatch(tool_name, tool_args, state['current_tree'])

    print(f'⚡ RESULT: {result.get("status")} — {result.get("message", "")}\n')

    # Determine new status
    status = state['status']
    pending_question = state.get('pending_question', '')
    pending_options = state.get('pending_options', [])

    if result['status'] == 'done':
        status = 'done'
    elif result['status'] == 'failed':
        status = 'failed'
    elif result['status'] == 'awaiting_user':
        status = 'awaiting_user'
        pending_question = result.get('message', '')
        pending_options = result.get('options', [])

    # Add tool result to message history
    messages = state['messages'].copy()
    messages.append({
        'role': 'tool',
        'tool_call_id': tool_call_id,
        'content': json.dumps(result),
    })

    return {
        'messages': messages,
        'last_tool_result': result,
        'status': status,
        'step_count': state['step_count'] + 1,
        'pending_question': pending_question,
        'pending_options': pending_options,
        '_pending_tool_call': {},
    }


def finalize(state: HarnessState) -> dict:
    """FINALIZE: Log completion and return final state."""
    status = state['status']
    result = state.get('last_tool_result', {})
    logger.info(f'FINALIZE: status={status}, message={result.get("message", "")}')

    icon = '✅' if status == 'done' else '❌'
    print(f'\n{icon} TASK {status.upper()}: {result.get("message", "")}\n')
    print(f'   Total steps: {state["step_count"]}')
    print(f'   Log: {state["execution_log_path"]}')

    return {}


# ---------------------------------------------------------------------------
# Conditional Edge Functions
# ---------------------------------------------------------------------------

def should_continue(state: HarnessState) -> str:
    """Determine next node after reason/execute."""
    status = state.get('status', 'running')

    if status in ('done', 'failed'):
        return 'finalize'
    elif status == 'awaiting_user':
        return 'finalize'  # For now, we finalize and let CLI handle user input
    else:
        return 'perceive'


def after_reason(state: HarnessState) -> str:
    """Determine next node after reason — execute tool or handle terminal."""
    if state.get('_pending_tool_call'):
        return 'execute_tool'
    else:
        return 'finalize'


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """Construct the LangGraph StateGraph for the cognitive loop.

    Graph structure:
        perceive → diff → reason → execute_tool → perceive (loop)
                                  → finalize (on done/fail/budget)
    """
    graph = StateGraph(HarnessState)

    # Add nodes
    graph.add_node('perceive', perceive)
    graph.add_node('diff', diff)
    graph.add_node('reason', reason)
    graph.add_node('execute_tool', execute_tool)
    graph.add_node('finalize', finalize)

    # Set entry point
    graph.set_entry_point('perceive')

    # Add edges
    graph.add_edge('perceive', 'diff')
    graph.add_edge('diff', 'reason')

    # After reason: either execute tool or finalize
    graph.add_conditional_edges('reason', after_reason, {
        'execute_tool': 'execute_tool',
        'finalize': 'finalize',
    })

    # After execute: either loop back to perceive or finalize
    graph.add_conditional_edges('execute_tool', should_continue, {
        'perceive': 'perceive',
        'finalize': 'finalize',
    })

    graph.add_edge('finalize', END)

    return graph


# ---------------------------------------------------------------------------
# High-Level Runner
# ---------------------------------------------------------------------------

def run_task(
    task: str,
    app_name: str | None = None,
    platform: str = 'macos',
    max_steps: int = 20,
    log_dir: str | None = None,
) -> HarnessState:
    """Run a complete task through the cognitive loop.

    Args:
        task: Natural language task instruction.
        app_name: Optional target application hint.
        platform: OS platform.
        max_steps: Maximum step budget.
        log_dir: Directory for execution logs. Defaults to ATree_tool/tasks/logs/.

    Returns:
        Final HarnessState after completion.
    """
    # Setup logging
    if log_dir is None:
        log_dir = os.path.join(os.path.dirname(__file__), '..', 'ATree_tool', 'tasks', 'logs')
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_name = task[:40].replace(' ', '_').replace('/', '_')
    log_path = os.path.join(log_dir, f'{safe_name}_{timestamp}.diff.log')

    # Load learnings
    learnings = load_learnings()

    # Build system prompt
    system_prompt = build_system_prompt(learnings=learnings, platform=platform)

    # Create initial state
    from llm_os.state import create_initial_state
    initial_state = create_initial_state(
        task=task,
        log_path=log_path,
        platform=platform,
        max_steps=max_steps,
    )
    initial_state['learnings'] = learnings
    initial_state['messages'] = [{'role': 'system', 'content': system_prompt}]

    # Store app hint for perceive node
    if app_name:
        initial_state['_app_hint'] = app_name

    print('=' * 60)
    print(f'🚀 LLM_OS HARNESS — Starting Task')
    print(f'   Task: {task}')
    print(f'   Model: {_get_model()}')
    print(f'   Budget: {max_steps} steps')
    print(f'   Log: {log_path}')
    print('=' * 60)

    # Build and compile graph
    graph = build_graph()
    app = graph.compile()

    # Run
    final_state = app.invoke(initial_state)

    return final_state


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _infer_app_name(state: HarnessState) -> str | None:
    """Simple heuristic to extract app name from task or state.

    In future iterations, the LLM could explicitly specify target apps.
    """
    # Check for explicit hint
    if state.get('_app_hint'):
        return state['_app_hint']

    # Simple keyword matching
    task_lower = state['task'].lower()
    app_keywords = {
        'calendar': 'Calendar',
        'finder': 'Finder',
        'safari': 'Safari',
        'notion': 'Notion',
        'vscode': 'Visual Studio Code',
        'vs code': 'Visual Studio Code',
        'visual studio code': 'Visual Studio Code',
        'whatsapp': 'WhatsApp',
        'telegram': 'Telegram',
        'brave': 'Brave Browser',
        'obs': 'OBS',
        'word': 'Microsoft Word',
        'system settings': 'System Settings',
        'system preferences': 'System Preferences',
    }
    for keyword, app_name in app_keywords.items():
        if keyword in task_lower:
            return app_name

    return None


def _manage_context_window(
    messages: list[dict],
    new_user_message: str,
    max_messages: int = 1,
) -> list[dict]:
    """Manage the LLM context window to prevent token explosion.

    Strategy (inspired by Agent-S flush_messages):
    - Always keep the system prompt (messages[0])
    - Keep the last `max_messages` conversation turns
    - Evict older turns that contain full tree dumps

    Args:
        messages: Current message list.
        new_user_message: The new user message to append.
        max_messages: Max conversation turns to retain (excluding system prompt).

    Returns:
        Updated message list with the new message appended.
    """
    result = []

    # Always keep system prompt
    if messages and messages[0].get('role') == 'system':
        result.append(messages[0])
        rest = messages[1:]
    else:
        rest = messages

    # Keep only the last N messages
    if len(rest) > max_messages:
        # Evict old messages, keeping a summary note
        evicted_count = len(rest) - max_messages
        result.append({
            'role': 'user',
            'content': f'[System note: {evicted_count} earlier conversation turns have been pruned to save context. '
                       f'The task remains: {new_user_message.split(chr(10))[0] if new_user_message else ""}]',
        })
        rest = rest[-max_messages:]

    result.extend(rest)

    # Append new user message
    result.append({
        'role': 'user',
        'content': new_user_message,
    })

    return result


def _message_to_dict(message) -> dict:
    """Convert an OpenAI ChatCompletion message to a serializable dict."""
    msg = {'role': message.role}

    if message.content:
        msg['content'] = message.content

    if message.tool_calls:
        msg['tool_calls'] = [
            {
                'id': tc.id,
                'type': 'function',
                'function': {
                    'name': tc.function.name,
                    'arguments': tc.function.arguments,
                },
            }
            for tc in message.tool_calls
        ]

    return msg
