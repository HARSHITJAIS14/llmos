"""
Subprocess wrappers for low-level OS interaction.
"""
import json
import subprocess
import os
import logging
from typing import Any, Dict, List

logger = logging.getLogger('llm_os.execution')

# Allow configuring the agent-desktop binary path via env var or default
AGENT_DESKTOP_BIN = os.environ.get(
    'AGENT_DESKTOP_BIN', 
    '/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js'
)
STEALTH_CLICK_BIN = os.path.join(
    os.path.dirname(__file__), '..', 'ATree_tool', 'utils', 'stealth_click'
)

def run_agent_cmd(args: List[str]) -> Dict[str, Any]:
    """
    Execute an agent-desktop CLI command and return parsed JSON result.
    
    Args:
        args: List of arguments to pass to the CLI.
        
    Returns:
        Parsed JSON dictionary response.
    """
    cmd = [AGENT_DESKTOP_BIN] + args
    logger.debug(f'Running: {" ".join(cmd)}')
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(res.stdout)
    except Exception as e:
        return {'ok': False, 'raw': res.stdout, 'error': str(e)}


def stealth_click(x: int, y: int) -> bool:
    """
    Perform a stealth click at (x, y) using the Swift binary.
    Moves mouse to target, clicks, and instantly restores original position.
    
    Args:
        x: The x-coordinate to click.
        y: The y-coordinate to click.
        
    Returns:
        True if successful, False otherwise.
    """
    try:
        result = subprocess.run(
            [STEALTH_CLICK_BIN, str(x), str(y)],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode != 0:
            logger.error(f'Stealth click failed at ({x}, {y}): {result.stderr or result.stdout}')
            return False
        return True
    except Exception as e:
        logger.error(f'Stealth click exception at ({x}, {y}): {e}')
        return False


def activate_app(app_name: str) -> None:
    """
    Force macOS to bring app to foreground using osascript reopen + activate.
    Critical for physical keystrokes/clicks to land in the correct app.
    
    Args:
        app_name: Name of the application to activate.
    """
    subprocess.run([
        'osascript',
        '-e', f'tell application "{app_name}" to reopen',
        '-e', f'tell application "{app_name}" to activate'
    ], check=True)


def open_url(url: str) -> None:
    """
    Open a URL using macOS `open` command.
    
    Args:
        url: The URL to open.
    """
    subprocess.run(['open', url], check=True)


def clipboard_set(text: str) -> Dict[str, Any]:
    """
    Set the system clipboard contents.
    
    Args:
        text: The text to copy to the clipboard.
        
    Returns:
        Parsed JSON dictionary response from the agent.
    """
    return run_agent_cmd(['clipboard-set', text])


def press_keys(keys: str) -> Dict[str, Any]:
    """
    Send keyboard shortcut via agent-desktop.
    
    Args:
        keys: keys format like 'cmd+v', 'return', 'cmd+shift+g'.
        
    Returns:
        Parsed JSON dictionary response from the agent.
    """
    return run_agent_cmd(['press', keys])


def run_shell_command(command: str, timeout: int = 15) -> Dict[str, Any]:
    """
    Execute an arbitrary bash command in a subprocess.
    
    Args:
        command: The shell command string.
        timeout: Maximum execution time in seconds.
        
    Returns:
        Dictionary with status, stdout, and stderr.
    """
    try:
        logger.info(f'Running shell command: {command}')
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            'status': 'ok' if result.returncode == 0 else 'error',
            'message': 'Command executed',
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {'status': 'error', 'message': f'Command timed out after {timeout} seconds'}
    except Exception as e:
        return {'status': 'error', 'message': f'Command failed: {e}'}
