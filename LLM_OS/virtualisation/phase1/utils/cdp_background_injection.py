import asyncio
import websockets
import json

async def inject_background_click(debugger_url: str, x: int, y: int):
    """
    Injects a click directly into an Electron/Chromium renderer via CDP.
    Bypasses macOS WindowServer entirely. Does not require keyWindow focus.
    """
    async with websockets.connect(debugger_url) as ws:
        # 1. Mouse Pressed
        await ws.send(json.dumps({
            "id": 1,
            "method": "Input.dispatchMouseEvent",
            "params": {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1}
        }))
        
        # 2. Mouse Released
        await ws.send(json.dumps({
            "id": 2,
            "method": "Input.dispatchMouseEvent",
            "params": {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1}
        }))
        print(f"Sub-50ms background click injected at ({x}, {y})")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python cdp_background_injection.py <debugger_url> <x> <y>")
        sys.exit(1)
    
    url = sys.argv[1]
    x = int(sys.argv[2])
    y = int(sys.argv[3])
    asyncio.run(inject_background_click(url, x, y))
