"""
fast_clicker.py
===============

An ultra-low latency, pure PyObjC implementation of the GroqClicker orchestrator.
This completely bypasses subprocesses, CLI commands, and disk I/O to achieve
perception-to-action execution in the theoretical minimum latency bounds.
"""

import os
import time
import base64
import requests
import json
import sys
import datetime
import Quartz
import Quartz.CoreGraphics as CG
from PIL import Image, ImageDraw
from io import BytesIO
from dotenv import load_dotenv

class FastGroqClicker:
    def __init__(self):
        """
        Initializes the FastGroqClicker by loading the API key, configuring the Groq endpoint,
        and setting up logging.
        """
        load_dotenv()
        self.api_key = os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable is missing.")
        
        self.model_id = "qwen/qwen3.8-27b"
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        self.log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
        os.makedirs(self.log_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(self.log_dir, f"fast_clicker_{timestamp}.log")
        
        with open(self.log_file, "w") as f:
            f.write(f"--- Starting FastGroqClicker Run at {timestamp} ---\n")
            
    def _log(self, msg):
        print(msg, flush=True)
        with open(self.log_file, "a") as f:
            f.write(msg + "\n")
            f.flush()

    def _get_window_screenshot(self, app_name):
        self._log(f"Finding visible window for {app_name} via PyObjC in-memory lookup...")
        step_start = time.time()
        
        # 1. Fast Memory Window Lookup
        options = CG.kCGWindowListOptionOnScreenOnly | CG.kCGWindowListExcludeDesktopElements
        window_list = CG.CGWindowListCopyWindowInfo(options, CG.kCGNullWindowID)
        
        target_win = None
        for win in window_list:
            owner = win.get(CG.kCGWindowOwnerName, "")
            if owner == app_name:
                layer = win.get(CG.kCGWindowLayer, 0)
                if layer == 0:
                    target_win = win
                    break
                    
        if not target_win:
            self._log(f"No visible windows found for {app_name}")
            return None
            
        win_id = target_win[CG.kCGWindowNumber]
        bounds_dict = target_win[CG.kCGWindowBounds]
        bounds = {"x": bounds_dict["X"], "y": bounds_dict["Y"], "width": bounds_dict["Width"], "height": bounds_dict["Height"]}
        
        self._log(f"Found visible window in {time.time() - step_start:.3f}s: ID={win_id}")
        
        # 2. Native CGImage Memory Capture
        step_start = time.time()
        cg_image = CG.CGWindowListCreateImage(
            CG.CGRectNull,
            CG.kCGWindowListOptionIncludingWindow,
            win_id,
            CG.kCGWindowImageBoundsIgnoreFraming | CG.kCGWindowImageBestResolution
        )
        self._log(f"Quartz CGImage pulled directly from WindowServer in {time.time() - step_start:.3f}s")
        
        if not cg_image:
            self._log("Failed to capture image")
            return None
            
        # 3. Direct CGImage to PIL Conversion (Zero Disk I/O)
        step_start = time.time()
        width = CG.CGImageGetWidth(cg_image)
        height = CG.CGImageGetHeight(cg_image)
        bytes_per_row = CG.CGImageGetBytesPerRow(cg_image)
        provider = CG.CGImageGetDataProvider(cg_image)
        data = CG.CGDataProviderCopyData(provider)
        
        pil_img = Image.frombuffer("RGBA", (width, height), data, "raw", "BGRA", bytes_per_row, 1)
        pil_img = pil_img.convert("RGB")
        
        self._log(f"Image parsed into PIL in {time.time() - step_start:.3f}s")
        return pil_img, bounds

    def _execute_stealth_click(self, x, y):
        step_start = time.time()
        self._log(f"🖱️ EXECUTING NATIVE PyObjC STEALTH MOUSE CLICK AT ({x}, {y})...")
        
        current_event = CG.CGEventCreate(None)
        original_loc = CG.CGEventGetLocation(current_event)
        target_loc = CG.CGPoint(x, y)
        
        # Warp, Click, Warp
        CG.CGWarpMouseCursorPosition(target_loc)
        time.sleep(0.01)
        
        source = CG.CGEventSourceCreate(CG.kCGEventSourceStateHIDSystemState)
        click_down = CG.CGEventCreateMouseEvent(source, CG.kCGEventLeftMouseDown, target_loc, CG.kCGMouseButtonLeft)
        click_up = CG.CGEventCreateMouseEvent(source, CG.kCGEventLeftMouseUp, target_loc, CG.kCGMouseButtonLeft)
        
        CG.CGEventPost(CG.kCGHIDEventTap, click_down)
        CG.CGEventPost(CG.kCGHIDEventTap, click_up)
        time.sleep(0.01)
        
        CG.CGWarpMouseCursorPosition(original_loc)
        self._log(f"Native stealth click executed in {time.time() - step_start:.3f}s")

    def click(self, task_instruction, app_name=None, resolution=(2048, 2048)):
        self._log(f"--- Task: {task_instruction} ---")
        
        # 1. Perception
        if app_name:
            result = self._get_window_screenshot(app_name)
            if not result: return None
            raw_img, bounds = result
        else:
            return None # Fast path requires targeted app window
            
        original_size = raw_img.size
        annotated_img = raw_img.copy()
        
        # Downscale & Encode
        step_start = time.time()
        raw_img.thumbnail(resolution)
        scale_x = original_size[0] / raw_img.size[0]
        scale_y = original_size[1] / raw_img.size[1]
        
        buffered = BytesIO()
        raw_img.save(buffered, format="JPEG", quality=85)
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        self._log(f"Image scaling and b64 encoding completed in {time.time() - step_start:.3f}s")
        
        # 2. Groq Payload with Few-Shot Prompting
        system_prompt = (
            "You are a fast UI executor for macOS. Analyze the provided screenshot. "
            "You MUST ALWAYS output a JSON object with EXACTLY three keys: "
            "'x' (integer), 'y' (integer), and 'status' (string: 'done' or 'failed'). "
            "NEVER use bbox_2d, arrays, or any other schema."
        )
        
        user_prompt = f"This is an isolated window of {app_name}. {task_instruction}" if app_name else task_instruction
        
        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Click on the 'settings' icon in the top right."},
                {"role": "assistant", "content": "{\"x\": 950, \"y\": 45, \"status\": \"done\"}"},
                {"role": "user", "content": "Find the 'buy now' button."},
                {"role": "assistant", "content": "{\"x\": 500, \"y\": 750, \"status\": \"done\"}"},
                {"role": "user", "content": "Click on the user profile picture."},
                {"role": "assistant", "content": "{\"x\": 120, \"y\": 80, \"status\": \"done\"}"},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt}, 
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]}
            ],
            "temperature": 0.0,
            "max_completion_tokens": 50,
            "response_format": {"type": "json_object"}
        }
        
        # 3. Fire Inference
        self._log(f"Firing request to Groq LPU API ({self.model_id})...")
        start_time = time.time()
        response = requests.post(self.api_url, headers=self.headers, json=payload)
        end_time = time.time()
        
        if response.status_code != 200:
            self._log(f"API Error: {response.status_code} - {response.text}")
            return None
            
        res_json = response.json()
        content = res_json["choices"][0]["message"]["content"]
        
        self._log(f"Total Groq Latency: {end_time - start_time:.3f} seconds")
        self._log(f"Raw Output: {content.strip()}")
        
        try:
            parsed = json.loads(content)
            model_x = None
            model_y = None
            
            if "x" in parsed and "y" in parsed:
                model_x = parsed["x"]
                model_y = parsed["y"]
            elif "bbox_2d" in parsed and len(parsed["bbox_2d"]) >= 2:
                model_x = parsed["bbox_2d"][0]
                model_y = parsed["bbox_2d"][1]
                
            if model_x is not None and model_y is not None:
                # Math
                local_x = int(model_x * scale_x)
                local_y = int(model_y * scale_y)
                abs_x = int(bounds["x"] + (local_x / 2))
                abs_y = int(bounds["y"] + (local_y / 2))
                
                self._log(f"Absolute Logical Screen Coordinates: X={abs_x}, Y={abs_y}")
                
                # Visual Debugging
                draw = ImageDraw.Draw(annotated_img)
                r = 30
                draw.ellipse([local_x-r, local_y-r, local_x+r, local_y+r], outline="red", width=10)
                draw.ellipse([local_x-5, local_y-5, local_x+5, local_y+5], fill="red")
                output_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "fast_click_result.jpg"))
                annotated_img.save(output_file)
                
                # 4. Action Execution
                self._execute_stealth_click(abs_x, abs_y)
                return (abs_x, abs_y)
            else:
                self._log("Model failed to find the target.")
                return None
        except Exception as e:
            self._log(f"Exception during parsing: {e}")
            return None

if __name__ == "__main__":
    task = "Click on the 'bet the whole fund on spacex' video"
    app = "Safari"
    if len(sys.argv) > 1: task = sys.argv[1]
    if len(sys.argv) > 2: app = sys.argv[2]
        
    clicker = FastGroqClicker()
    clicker.click(task, app_name=app)
