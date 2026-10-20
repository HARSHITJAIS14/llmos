"""
clicker.py
==========

This module implements the primary `GroqClicker` orchestrator. It is responsible for bridging
native macOS UI interactions (window detection, screenshotting, mouse clicking) with
a fast Vision-Language Model (VLM) via the Groq API.

It utilizes the `agent-desktop-darwin-arm64` binary to locate specific application windows,
`screencapture` to take low-latency retina screenshots, and a custom `stealth_click` Swift binary
to execute mouse clicks without visually hijacking the user's cursor.
"""

import os
import time
import base64
import requests
import json
import sys
import subprocess
import datetime
from PIL import ImageGrab, ImageDraw, Image
from io import BytesIO

class GroqClicker:
    """
    A fast UI executor that leverages Groq's LPU endpoints for coordinate prediction.
    
    This class handles the end-to-end loop:
    1. Finding and isolating the target macOS application window.
    2. Taking an isolated, retina-quality screenshot of the window.
    3. Downscaling and transmitting the image to a VLM (qwen3.8-27b).
    4. Mapping the predicted internal coordinates back to absolute, logical macOS screen space.
    5. Firing a stealth hardware click at the target location.
    """
    
    def __init__(self):
        """
        Initializes the GroqClicker by loading the API key, configuring the Groq endpoint,
        and resolving paths to the required native macOS binaries (agent-desktop and stealth_click).
        Also initializes a unique log file for the current run session.
        """
        self.api_key = os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable is missing.")
        
        self.model_id = "qwen/qwen3.8-27b"
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Point directly to the Rust binary to save ~30ms of Node.js boot overhead
        self.agent_desktop = "/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop-darwin-arm64"
        
        # Point to the local compiled stealth_click binary
        self.stealth_click_bin = os.path.abspath(os.path.join(os.path.dirname(__file__), "stealth_click"))
        
        # Setup logging directory and file
        self.log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
        os.makedirs(self.log_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(self.log_dir, f"clicker_{timestamp}.log")
        
        with open(self.log_file, "w") as f:
            f.write(f"--- Starting GroqClicker Run at {timestamp} ---\n")
            
    def _log(self, msg):
        """
        Helper method to print a message to the console and simultaneously append it
        to the session's log file to ensure all step timings are recorded.
        """
        print(msg, flush=True)
        with open(self.log_file, "a") as f:
            f.write(msg + "\n")
            f.flush()

    def _get_window_screenshot(self, app_name):
        """
        Locates the currently active window for the specified macOS application, retrieves its bounding box,
        and takes an isolated screenshot using the native macOS `screencapture` utility.

        Args:
            app_name (str): The name of the macOS application (e.g., "Safari").

        Returns:
            tuple: A tuple containing (output_image_path, window_bounds_dict), or None if it fails.
        """
        self._log(f"Finding visible window for {app_name} via agent-desktop...")
        step_start = time.time()
        
        # Activate app to ensure it's ready and foregrounded
        subprocess.run(["osascript", "-e", f'tell application "{app_name}" to activate'])
        
        # Use agent-desktop to list the app's windows and get spatial bounds
        result = subprocess.run(
            [self.agent_desktop, "list-windows", "--app", app_name],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            self._log(f"Failed to list windows: {result.stderr}")
            return None
            
        data = json.loads(result.stdout)
        windows = data.get("data", [])
        
        # Find the first visible window in the list
        target_win = next((w for w in windows if w.get("visible")), None)
        if not target_win:
            self._log(f"No visible windows found for {app_name}")
            return None
            
        win_id = target_win["id"]
        self._log(f"Found visible window in {time.time() - step_start:.3f}s: {win_id} ({target_win.get('title', 'Unknown')})")
        
        # Take isolated screenshot of just this window using native macOS screencapture
        step_start = time.time()
        out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "app_screenshot_raw.png"))
        
        # Extract native CGWindowID (e.g. "w-4106" -> "4106") for screencapture targeted window mode
        cg_win_id = win_id.replace("w-", "")
        subprocess.run(["screencapture", "-l", cg_win_id, out_path])
        
        if not os.path.exists(out_path):
            self._log("Failed to capture window screenshot.")
            return None
            
        self._log(f"Native screencapture captured in {time.time() - step_start:.3f}s")
        return out_path, target_win["bounds"]

    def click(self, task_instruction, app_name=None, resolution=(1024, 1024)):
        """
        Executes the complete perception-to-action pipeline based on a natural language instruction.
        Takes a screenshot, passes it to the Groq VLM for coordinate prediction, maps the coordinates,
        draws a visual verification target, and executes a hardware click.

        Args:
            task_instruction (str): The natural language instruction (e.g., "Click on the settings icon").
            app_name (str, optional): The target application to isolate. Defaults to None (full screen).
            resolution (tuple): The target resolution to downscale the image to before sending to the VLM.

        Returns:
            tuple: The final absolute logical coordinates (x, y) that were clicked, or None on failure.
        """
        self._log(f"--- Task: {task_instruction} ---")
        
        # 1. Capture Image
        if app_name:
            result = self._get_window_screenshot(app_name)
            if not result:
                return None
            img_path, bounds = result
            raw_img = Image.open(img_path).convert("RGB")
        else:
            self._log("Capturing full screen screenshot...")
            raw_img = ImageGrab.grab().convert("RGB")
            bounds = {"x": 0, "y": 0, "width": raw_img.width, "height": raw_img.height}
            
        original_size = raw_img.size
        annotated_img = raw_img.copy()
        
        # Downscale for API latency optimization
        step_start = time.time()
        raw_img.thumbnail(resolution)
        scale_x = original_size[0] / raw_img.size[0]
        scale_y = original_size[1] / raw_img.size[1]
        
        buffered = BytesIO()
        raw_img.save(buffered, format="JPEG", quality=85)
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        self._log(f"Image scaling and b64 encoding completed in {time.time() - step_start:.3f}s")
        
        # 2. Build Payload
        context = "You are a fast UI executor for macOS. Analyze the provided screenshot."
        if app_name:
            context += f" This is an isolated window of {app_name}."
            
        prompt_str = f"{context} {task_instruction} Output ONLY a valid JSON object with keys 'x' and 'y' representing absolute pixel coordinates relative to the top-left of this image, and 'status' (done/failed)."
        
        payload = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_str},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                    ]
                }
            ],
            "temperature": 0.0,
            "max_completion_tokens": 50,
            "response_format": {"type": "json_object"}
        }
        
        # 3. Fire Request to VLM
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
            if "x" in parsed and "y" in parsed:
                model_x = parsed["x"]
                model_y = parsed["y"]
                
                # Scale coordinates back up to the original window's retina resolution
                local_x = int(model_x * scale_x)
                local_y = int(model_y * scale_y)
                
                # Calculate absolute screen coordinates.
                # Retina display coordinate mapping for hardware clicks requires dividing the pixel offsets by 2
                abs_x = int(bounds["x"] + (local_x / 2))
                abs_y = int(bounds["y"] + (local_y / 2))
                
                self._log(f"Mapped to Window Resolution: X={local_x}, Y={local_y}")
                self._log(f"Absolute Logical Screen Coordinates: X={abs_x}, Y={abs_y}")
                
                # Draw a visual "click" marker on the screenshot so the user can verify accuracy
                draw = ImageDraw.Draw(annotated_img)
                r = 30 # Radius of the click circle
                draw.ellipse([local_x-r, local_y-r, local_x+r, local_y+r], outline="red", width=10)
                draw.ellipse([local_x-5, local_y-5, local_x+5, local_y+5], fill="red") # Center dot
                
                output_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "click_result.jpg"))
                annotated_img.save(output_file)
                self._log(f"✅ Saved visual verification to {output_file}")
                
                # 4. Execute Hardware Click
                # Uses the local stealth_click swift binary to teleport, click, and return the pointer instantly.
                step_start = time.time()
                self._log(f"🖱️ EXECUTING STEALTH MOUSE CLICK AT ({abs_x}, {abs_y})...")
                subprocess.run([self.stealth_click_bin, str(abs_x), str(abs_y)])
                self._log(f"Stealth click executed in {time.time() - step_start:.3f}s")
                
                return (abs_x, abs_y)
            else:
                self._log("Model failed to find the target.")
                return None
        except Exception as e:
            self._log(f"Failed to parse JSON: {e}")
            return None

if __name__ == "__main__":
    task = "Find the Apple menu icon (top left)."
    app = None
    
    # Simple CLI parser to allow testing from the terminal
    if len(sys.argv) > 1:
        task = sys.argv[1]
    if len(sys.argv) > 2:
        app = sys.argv[2]
        
    clicker = GroqClicker()
    clicker.click(task, app_name=app)
