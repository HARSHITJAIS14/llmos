"""
LLM_OS Agent-Computer Interface (ACI).

Defines the structured tool schemas that the LLM can invoke via JSON tool calling,
and the dispatch router that maps tool calls to concrete OS-level actions.

Inspired by Agent-S's @agent_action pattern, but using native OpenAI/Anthropic
tool schemas instead of eval()/exec().
"""
import logging
import time
from typing import Any, Optional

from llm_os.execution import (
    run_agent_cmd,
    stealth_click as _stealth_click,
    activate_app as _activate_app,
    clipboard_set as _clipboard_set,
    press_keys as _press_keys,
    open_url as _open_url,
)
from llm_os.perception import find_node_by_ref_id, get_node_center

logger = logging.getLogger('llm_os.aci')


# ---------------------------------------------------------------------------
# Tool Schema Definitions (OpenAI function calling format)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "semantic_click",
            "description": (
                "Dispatch a semantic AXPress click on a UI element by its ref_id. "
                "This works in the background without stealing user focus. "
                "Use this for native/Catalyst apps (Finder, Calendar, Safari, OBS). "
                "WARNING: Semantic clicks are silently swallowed by Electron/React apps (Notion, VS Code) — "
                "use stealth_click for those instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ref_id": {
                        "type": "string",
                        "description": "The ref_id of the AX tree node to click."
                    }
                },
                "required": ["ref_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stealth_click",
            "description": (
                "Perform a physical coordinate click on a UI element identified by ref_id. "
                "Reads the element's bounding box from the current AX tree, computes the center, "
                "and executes a stealth click (click + instant mouse restore). "
                "Use this for Electron/React apps where semantic AXPress is swallowed. "
                "The element MUST have valid bounds (not offscreen). "
                "If the element is offscreen, use scroll_to first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ref_id": {
                        "type": "string",
                        "description": "The ref_id of the AX tree node to click."
                    }
                },
                "required": ["ref_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stealth_click_xy",
            "description": (
                "Perform a physical stealth click at explicit (x, y) pixel coordinates. "
                "Use only when you already know the exact coordinates from the AX tree bounds."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X pixel coordinate."},
                    "y": {"type": "integer", "description": "Y pixel coordinate."}
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": (
                "Inject text directly into a text field using semantic set-value. "
                "This sets the accessibility value of the node without requiring focus or keyboard events. "
                "Works for native text fields but may fail on Electron/React controlled inputs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ref_id": {
                        "type": "string",
                        "description": "The ref_id of the text field node."
                    },
                    "text": {
                        "type": "string",
                        "description": "The text to inject."
                    }
                },
                "required": ["ref_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "clipboard_paste",
            "description": (
                "Set the system clipboard to the given text, activate the target app, "
                "and paste with Cmd+V. This is the most reliable text injection method, "
                "especially for Electron apps and search bars. "
                "ALWAYS activates the app before pasting to prevent keystroke leakage."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to paste."
                    },
                    "app_name": {
                        "type": "string",
                        "description": "The application to activate before pasting (e.g. 'Calendar', 'Notion')."
                    }
                },
                "required": ["text", "app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "press_keys",
            "description": (
                "Send a keyboard shortcut or key press. "
                "Format: 'cmd+v', 'return', 'cmd+shift+g', 'cmd+n', 'escape'. "
                "If app_name is provided, the app is activated first to ensure keystrokes "
                "land in the correct window (critical for physical keystrokes)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "string",
                        "description": "Key combo string (e.g. 'cmd+v', 'return', 'cmd+shift+g')."
                    },
                    "app_name": {
                        "type": "string",
                        "description": "Optional: activate this app before pressing keys."
                    }
                },
                "required": ["keys"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "activate_app",
            "description": (
                "Force macOS to bring an application to the foreground. "
                "Uses osascript reopen + activate to ensure the app's main window exists and is focused. "
                "NEVER use this before semantic clicks (AXPress) — it will unnecessarily steal user focus. "
                "ALWAYS use this before physical keystrokes or coordinate clicks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "The application name (e.g. 'Calendar', 'Visual Studio Code', 'Notion')."
                    }
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scroll_to",
            "description": (
                "Scroll a UI element into view. Use when a node is offscreen (has 'offscreen' in states "
                "or height: 0 in bounds). After scrolling, you MUST re-perceive (take a new snapshot) "
                "to get updated bounds before clicking."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ref_id": {
                        "type": "string",
                        "description": "The ref_id of the offscreen element to scroll into view."
                    }
                },
                "required": ["ref_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wait",
            "description": (
                "Wait for a specified duration before the next perception step. "
                "Use when waiting for an animation, page load, or UI transition to complete."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "number",
                        "description": "Duration to wait in seconds (e.g. 1.0, 2.5)."
                    }
                },
                "required": ["seconds"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": (
                "Signal that the task has been completed successfully. "
                "Call this ONLY after verifying the final state confirms task success."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Brief summary of what was accomplished."
                    }
                },
                "required": ["summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fail",
            "description": (
                "Signal that the task cannot be completed. "
                "Use when an unrecoverable error is encountered or the target element cannot be found."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Explanation of why the task failed."
                    }
                },
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": (
                "Pause execution and ask the user for clarification or disambiguation. "
                "MANDATORY when multiple candidate elements match a search query (e.g. multiple contacts "
                "named 'Vivek'). NEVER guess ambiguous targets — always ask."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to present to the user."
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of options for the user to choose from."
                    }
                },
                "required": ["question", "options"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a bash script or terminal command using subprocess.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The bash command to run."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write text content to a file on disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file."},
                    "content": {"type": "string", "description": "The content to write."}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_element",
            "description": "Query the in-memory AX tree directly for an element's coordinates without taking a new snapshot. Very fast.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "description": "The role to search for (e.g. 'button')."},
                    "name": {"type": "string", "description": "The name or text of the element."}
                },
                "required": ["role", "name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_learnings",
            "description": "Permanently record a hard-learned lesson or workaround about the OS or apps to learnings.md so you don't forget it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lesson": {"type": "string", "description": "The lesson to record."}
                },
                "required": ["lesson"]
            }
        }
    },
]

# Dynamically inject the 'thought' Chain-of-Thought scratchpad into ALL tools
for schema in TOOL_SCHEMAS:
    props = schema["function"]["parameters"].setdefault("properties", {})
    req = schema["function"]["parameters"].setdefault("required", [])
    props["thought"] = {
        "type": "string", 
        "description": "Scratchpad. Think out loud about the current UI state and what you must do next before taking action."
    }
    if "thought" not in req:
        req.insert(0, "thought")


def get_tool_names() -> list[str]:
    """Return all registered tool names."""
    return [t['function']['name'] for t in TOOL_SCHEMAS]


def get_tool_descriptions() -> str:
    """Return formatted tool descriptions for inclusion in system prompts."""
    lines = []
    for schema in TOOL_SCHEMAS:
        func = schema['function']
        name = func['name']
        desc = func['description']
        params = func['parameters']['properties']
        required = func['parameters'].get('required', [])

        param_strs = []
        for pname, pinfo in params.items():
            req_marker = ' (required)' if pname in required else ' (optional)'
            param_strs.append(f'    - {pname}: {pinfo.get("type", "any")} — {pinfo.get("description", "")}{req_marker}')

        lines.append(f'### {name}\n{desc}\n  Parameters:\n' + '\n'.join(param_strs))

    return '\n\n'.join(lines)


# ---------------------------------------------------------------------------
# Tool Dispatch Router
# ---------------------------------------------------------------------------

def dispatch(
    tool_name: str,
    arguments: dict[str, Any],
    current_tree: dict,
) -> dict:
    """Route a tool call to its concrete implementation.

    Args:
        tool_name: The name of the tool to execute.
        arguments: The tool arguments from the LLM.
        current_tree: The current AX tree (needed for ref_id → bounds resolution).

    Returns:
        Result dict with at minimum: {"status": "ok"|"error", "message": "..."}.
    """
    logger.info(f'Dispatching tool: {tool_name}({arguments})')

    try:
        match tool_name:
            # --- Click Actions ---
            case 'semantic_click':
                result = run_agent_cmd(['click', arguments['ref_id']])
                return _wrap_result(result, f'Semantic click on {arguments["ref_id"]}')

            case 'stealth_click':
                ref_id = arguments['ref_id']
                node = find_node_by_ref_id(current_tree, ref_id)
                if not node:
                    return {'status': 'error', 'message': f'Node not found: {ref_id}'}
                center = get_node_center(node)
                if not center:
                    return {'status': 'error', 'message': f'Node has no bounds: {ref_id}. Try scroll_to first.'}
                x, y = center
                success = _stealth_click(x, y)
                return {
                    'status': 'ok' if success else 'error',
                    'message': f'Stealth click at ({x}, {y}) for {ref_id}',
                    'coordinates': {'x': x, 'y': y},
                }

            case 'stealth_click_xy':
                success = _stealth_click(arguments['x'], arguments['y'])
                return {
                    'status': 'ok' if success else 'error',
                    'message': f'Stealth click at ({arguments["x"]}, {arguments["y"]})',
                }

            # --- Text Input Actions ---
            case 'type_text':
                result = run_agent_cmd(['set-value', arguments['ref_id'], arguments['text']])
                return _wrap_result(result, f'Set value on {arguments["ref_id"]}')

            case 'clipboard_paste':
                _clipboard_set(arguments['text'])
                _activate_app(arguments['app_name'])
                time.sleep(0.3)
                result = _press_keys('cmd+v')
                return _wrap_result(result, f'Clipboard paste into {arguments["app_name"]}')

            # --- Keyboard Actions ---
            case 'press_keys':
                app_name = arguments.get('app_name')
                if app_name:
                    _activate_app(app_name)
                    time.sleep(0.3)
                result = _press_keys(arguments['keys'])
                return _wrap_result(result, f'Press {arguments["keys"]}')

            # --- App Management ---
            case 'activate_app':
                _activate_app(arguments['app_name'])
                return {'status': 'ok', 'message': f'Activated {arguments["app_name"]}'}

            case 'scroll_to':
                result = run_agent_cmd(['scroll-to', arguments['ref_id']])
                return _wrap_result(result, f'Scrolled to {arguments["ref_id"]}')

            # --- Control Flow ---
            case 'wait':
                seconds = arguments['seconds']
                time.sleep(seconds)
                return {'status': 'ok', 'message': f'Waited {seconds}s'}

            case 'done':
                return {'status': 'done', 'message': arguments['summary']}

            case 'fail':
                return {'status': 'failed', 'message': arguments['reason']}

            case 'ask_user':
                return {
                    'status': 'awaiting_user',
                    'message': arguments['question'],
                    'options': arguments.get('options', []),
                }

            # --- Backend Developer Tools ---
            case 'run_command':
                from llm_os.execution import run_shell_command
                return run_shell_command(arguments['command'])

            case 'read_file':
                try:
                    with open(arguments['path'], 'r', encoding='utf-8') as f:
                        content = f.read()
                    # Truncate if massive
                    if len(content) > 5000:
                        content = content[:5000] + '\n... [TRUNCATED]'
                    return {'status': 'ok', 'message': f'Read file {arguments["path"]}', 'content': content}
                except Exception as e:
                    return {'status': 'error', 'message': f'Failed to read {arguments["path"]}: {e}'}

            case 'write_file':
                try:
                    with open(arguments['path'], 'w', encoding='utf-8') as f:
                        f.write(arguments['content'])
                    return {'status': 'ok', 'message': f'Wrote file {arguments["path"]}'}
                except Exception as e:
                    return {'status': 'error', 'message': f'Failed to write {arguments["path"]}: {e}'}

            case 'find_element':
                from llm_os.perception import find_node_by_name
                role = arguments.get('role')
                name = arguments.get('name')
                node = find_node_by_name(current_tree, name, role)
                if not node:
                    return {'status': 'error', 'message': f'Element not found: role="{role}", name="{name}"'}
                
                center = get_node_center(node)
                return {
                    'status': 'ok',
                    'message': f'Found element: ref_id={node.get("ref_id")}',
                    'node': node,
                    'center': {'x': center[0], 'y': center[1]} if center else None
                }

            case 'update_learnings':
                import os
                # Determine learnings path
                learnings_path = os.path.join(os.path.dirname(__file__), '..', 'ATree_tool', 'learnings', 'learnings.md')
                # If run from root, we might want to check `.agents/learnings.md`, but ATree_tool is the default
                try:
                    with open(learnings_path, 'a', encoding='utf-8') as f:
                        f.write(f"\n- {arguments['lesson']}")
                    return {'status': 'ok', 'message': 'Learnings updated successfully.'}
                except Exception as e:
                    return {'status': 'error', 'message': f'Failed to update learnings: {e}'}

            case _:
                return {'status': 'error', 'message': f'Unknown tool: {tool_name}'}

    except Exception as e:
        logger.exception(f'Tool dispatch error: {tool_name}')
        return {'status': 'error', 'message': f'Exception in {tool_name}: {str(e)}'}


def _wrap_result(raw_result: dict, description: str) -> dict:
    """Wrap an agent-desktop CLI result into a standardized format."""
    if raw_result.get('ok'):
        return {'status': 'ok', 'message': description, 'raw': raw_result}
    else:
        error = raw_result.get('error', raw_result.get('raw', 'Unknown error'))
        return {'status': 'error', 'message': f'{description} — {error}', 'raw': raw_result}
