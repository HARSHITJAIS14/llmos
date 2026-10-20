import subprocess
import os

STEALTH_CLICK_BIN = os.path.join(os.path.dirname(__file__), 'stealth_click')

def stealth_click(x, y):
    """
    Perform a "stealth click" at the specified (x, y) coordinates.
    This moves the mouse to the coordinates, clicks, and instantly restores
    the original mouse position to avoid interrupting the user's workflow.
    
    :param x: The x coordinate
    :param y: The y coordinate
    :return: True if the click executed successfully, False otherwise
    """
    try:
        result = subprocess.run(
            [STEALTH_CLICK_BIN, str(x), str(y)],
            capture_output=True,
            text=True,
            timeout=2
        )
        
        if result.returncode != 0:
            print(f"Stealth click failed at ({x}, {y}): {result.stderr or result.stdout}")
            return False
            
        return True
        
    except Exception as e:
        print(f"Stealth click encountered an exception at ({x}, {y}): {e}")
        return False
