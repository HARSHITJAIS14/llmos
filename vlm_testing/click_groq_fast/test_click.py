import Quartz
import Quartz.CoreGraphics as CG
import time
import sys

def pyobjc_stealth_click(x, y):
    print(f"Executing PyObjC stealth click at {x}, {y}")
    start = time.time()
    
    # 1. Get original mouse location
    current_event = CG.CGEventCreate(None)
    original_loc = CG.CGEventGetLocation(current_event)
    
    target_loc = CG.CGPoint(x, y)
    
    # 2. Warp to target
    CG.CGWarpMouseCursorPosition(target_loc)
    time.sleep(0.01) # 10ms wait
    
    # 3. Create click events
    source = CG.CGEventSourceCreate(CG.kCGEventSourceStateHIDSystemState)
    click_down = CG.CGEventCreateMouseEvent(source, CG.kCGEventLeftMouseDown, target_loc, CG.kCGMouseButtonLeft)
    click_up = CG.CGEventCreateMouseEvent(source, CG.kCGEventLeftMouseUp, target_loc, CG.kCGMouseButtonLeft)
    
    # Post events
    CG.CGEventPost(CG.kCGHIDEventTap, click_down)
    CG.CGEventPost(CG.kCGHIDEventTap, click_up)
    
    time.sleep(0.01) # 10ms wait
    
    # 4. Warp back
    CG.CGWarpMouseCursorPosition(original_loc)
    
    print(f"Click executed in {time.time()-start:.4f}s")
    
if __name__ == "__main__":
    if len(sys.argv) > 2:
        pyobjc_stealth_click(float(sys.argv[1]), float(sys.argv[2]))
    else:
        print("Usage: python3 test_click.py <x> <y>")
