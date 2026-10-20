import Quartz
import Quartz.CoreGraphics as CG
from PIL import Image
import time

def test_screenshot():
    start = time.time()
    # 1. Get window info
    options = CG.kCGWindowListOptionOnScreenOnly | CG.kCGWindowListExcludeDesktopElements
    window_list = CG.CGWindowListCopyWindowInfo(options, CG.kCGNullWindowID)
    
    # Find Safari
    target_win = None
    for win in window_list:
        owner = win.get(CG.kCGWindowOwnerName, "")
        if owner == "Safari":
            # Need a visible window
            layer = win.get(CG.kCGWindowLayer, 0)
            if layer == 0: # Standard window
                target_win = win
                break
                
    if not target_win:
        print("Safari not found")
        return
        
    win_id = target_win[CG.kCGWindowNumber]
    bounds = target_win[CG.kCGWindowBounds]
    print(f"Found Safari window ID {win_id} at {bounds} in {time.time()-start:.4f}s")
    
    # 2. Take screenshot of just that window
    cg_start = time.time()
    cg_image = CG.CGWindowListCreateImage(
        CG.CGRectNull,
        CG.kCGWindowListOptionIncludingWindow,
        win_id,
        CG.kCGWindowImageBoundsIgnoreFraming | CG.kCGWindowImageBestResolution
    )
    print(f"CGImage captured in {time.time()-cg_start:.4f}s")
    
    if not cg_image:
        print("Failed to capture image")
        return
        
    # 3. Convert to PIL
    pil_start = time.time()
    width = CG.CGImageGetWidth(cg_image)
    height = CG.CGImageGetHeight(cg_image)
    bytes_per_row = CG.CGImageGetBytesPerRow(cg_image)
    
    provider = CG.CGImageGetDataProvider(cg_image)
    data = CG.CGDataProviderCopyData(provider)
    
    # CoreGraphics returns BGRA format usually
    # PIL frombuffer requires careful stride alignment
    img = Image.frombuffer(
        "RGBA",
        (width, height),
        data,
        "raw",
        "BGRA",
        bytes_per_row,
        1
    )
    
    img = img.convert("RGB") # Drop alpha channel
    print(f"Converted to PIL Image {img.size} in {time.time()-pil_start:.4f}s")
    
    print(f"Total time: {time.time()-start:.4f}s")
    
    img.save("test_out.jpg", format="JPEG")
    
if __name__ == "__main__":
    test_screenshot()
