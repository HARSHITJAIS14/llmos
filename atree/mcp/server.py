#!/usr/bin/env python3
"""atree MCP server — the same fat tools `ax` gives Claude Code, exposed
over the Model Context Protocol for every other host: Antigravity, Gemini CLI,
Codex, Cursor, Claude Desktop.

Zero dependencies: a hand-rolled JSON-RPC 2.0 stdio loop (initialize,
tools/list, tools/call, ping). Each tool shells out to scripts/ax.py so the
behavior is identical across hosts — ghost-window handling, Electron
drill-down, husk detection, declare+act+verify, registry deposits.

Register (Antigravity: agent panel -> MCP servers; others: mcpServers config):

  {"mcpServers": {"atree": {"command": "python3",
      "args": ["/Users/harshit/Desktop/YC/atree/mcp/server.py"]}}}
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

AX = str(Path(__file__).resolve().parents[1] / "scripts" / "ax.py")
PROTOCOL = "2024-11-05"

TOOLS = [
    {
        "name": "ax_recall",
        "description": "ALWAYS CALL FIRST for any macOS desktop task. Returns what atree "
                       "already knows: L1 (exact route to replay), L2 (known elements with "
                       "working reach strategies), L3 (app known, discover), or miss (cold). On L3/miss, call ax_guide with the app name before discovering.",
        "inputSchema": {"type": "object", "properties": {
            "task": {"type": "string", "description": "the task in plain language"},
            "app": {"type": "string", "description": "target app name, if known"}},
            "required": ["task"]},
    },
    {
        "name": "ax_observe",
        "description": "Perceive an app's UI via the accessibility tree: compact digest of "
                       "interactive elements on first look, a diff of what changed on every "
                       "later look. Handles ghost windows and Electron drill-down. NEVER use "
                       "a screenshot to see the UI — use this.",
        "inputSchema": {"type": "object", "properties": {
            "app": {"type": "string"},
            "surface_focused": {"type": "boolean", "description": "scope to the focused surface (after a Space switch)"}},
            "required": ["app"]},
    },
    {
        "name": "ax_find",
        "description": "Locate a click/type target by visible text: returns role, name, "
                       "ref id (for semantic clicks) and center coordinates (for physical "
                       "clicks). NEVER screenshot to find an element — use this.",
        "inputSchema": {"type": "object", "properties": {
            "app": {"type": "string"},
            "text": {"type": "string"},
            "role": {"type": "string", "description": "optional role filter, e.g. button"}},
            "required": ["app", "text"]},
    },
    {
        "name": "ax_open",
        "description": "Launch or activate a macOS app and verify a window is frontmost. "
                       "THE only way to open an app: it uses AppleScript reopen+activate "
                       "(launches if not running, restores a closed window, brings it to "
                       "front, atomically). NEVER open an app via Spotlight (Cmd+Space), "
                       "the Dock, Launchpad, or any UI navigation — those are slow, "
                       "unreliable, and pollute the user's search history.",
        "inputSchema": {"type": "object", "properties": {
            "app": {"type": "string", "description": "exact app name, e.g. 'Notion', 'Safari'"}},
            "required": ["app"]},
    },
    {
        "name": "ax_guide",
        "description": "atree's domain knowledge on demand — months of macOS automation "
                       "learnings (per-app-archetype quirks, working strategies, traps). "
                       "CALL THIS BEFORE automating an app you haven't driven this session: "
                       "pass the app name (e.g. 'Notion', 'Safari', 'OBS') or a topic "
                       "('dialogs', 'rich-text', 'cli', 'index'). Electron apps swallow "
                       "clicks, ghost windows time out, save sheets have known patterns — "
                       "this tool tells you which, so you don't rediscover them.",
        "inputSchema": {"type": "object", "properties": {
            "topic": {"type": "string", "description": "app name or topic; 'index' lists archetypes"}},
            "required": ["topic"]},
    },
    {
        "name": "ax_type",
        "description": "THE way to enter text into any app. Pastes atomically via the "
                       "clipboard (clipboard-set + Cmd+V): one call for any length, real "
                       "input events so Electron/React apps register it, and the user's "
                       "clipboard is restored afterwards. NEVER type text character by "
                       "character with key presses — that is slow, error-prone, and an "
                       "anti-pattern this tool exists to replace. Focus the target field "
                       "first (ax_do a click), then call this.",
        "inputSchema": {"type": "object", "properties": {
            "app": {"type": "string"},
            "text": {"type": "string", "description": "the full text to enter, any length"},
            "postcondition": {"type": "object", "description":
                "optional check that the text landed; defaults to waiting for the text to render"}},
            "required": ["app", "text"]},
    },
    {
        "name": "ax_do",
        "description": "Execute ONE agent-desktop action with verification: declares the "
                       "postcondition, activates the app for physical input, runs the action, "
                       "then checks the postcondition against fresh AX state. Fails loudly "
                       "with a diagnosis if the action did not land — never claim success "
                       "that this tool did not verify. Example action: 'mouse-click --xy 295,647' "
                       "or 'press cmd+l' or 'click @s1:e42'. For entering TEXT, use ax_type "
                       "instead — never a sequence of per-character key presses.",
        "inputSchema": {"type": "object", "properties": {
            "postcondition": {"type": "object", "description":
                "{kind: node_exists|node_absent|value_equals|value_contains|title_matches, "
                "expect: {...}, app: str, timeout_ms?: int, description?: str}"},
            "action": {"type": "string", "description": "agent-desktop action args, e.g. 'press cmd+p'"}},
            "required": ["postcondition", "action"]},
    },
]


def run_ax(args: list[str]) -> tuple[str, bool]:
    res = subprocess.run([sys.executable, AX] + args, capture_output=True, text=True, timeout=120)
    out = (res.stdout + (("\n" + res.stderr) if res.stderr else "")).strip()
    return out or "(no output)", res.returncode == 0


def call_tool(name: str, a: dict) -> tuple[str, bool]:
    if name == "ax_recall":
        return run_ax(["recall", a["task"]] + ([a["app"]] if a.get("app") else []))
    if name == "ax_observe":
        return run_ax(["observe", a["app"]] + (["--surface", "focused"] if a.get("surface_focused") else []))
    if name == "ax_find":
        return run_ax(["find", a["app"], a["text"]] + ([a["role"]] if a.get("role") else []))
    if name == "ax_open":
        return run_ax(["open", a["app"]])
    if name == "ax_guide":
        return run_ax(["guide", a.get("topic", "index")])
    if name == "ax_type":
        extra = [json.dumps(a["postcondition"])] if a.get("postcondition") else []
        return run_ax(["type", a["app"], a["text"]] + extra)
    if name == "ax_do":
        import shlex
        return run_ax(["do", json.dumps(a["postcondition"]), "--"] + shlex.split(a["action"]))
    return f"unknown tool {name}", False


def reply(msg_id, result=None, error=None):
    out = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        out["error"] = error
    else:
        out["result"] = result
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        method, msg_id = msg.get("method"), msg.get("id")
        if method == "initialize":
            reply(msg_id, {"protocolVersion": PROTOCOL,
                           "capabilities": {"tools": {}},
                           "serverInfo": {"name": "atree", "version": "0.2.0"}})
        elif method in ("notifications/initialized", "notifications/cancelled"):
            continue  # notifications get no response
        elif method == "ping":
            reply(msg_id, {})
        elif method == "tools/list":
            reply(msg_id, {"tools": TOOLS})
        elif method == "tools/call":
            params = msg.get("params", {})
            try:
                text, ok = call_tool(params.get("name", ""), params.get("arguments", {}) or {})
            except Exception as exc:
                text, ok = f"tool crashed: {exc}", False
            reply(msg_id, {"content": [{"type": "text", "text": text}], "isError": not ok})
        elif msg_id is not None:
            reply(msg_id, error={"code": -32601, "message": f"method not found: {method}"})


if __name__ == "__main__":
    main()
