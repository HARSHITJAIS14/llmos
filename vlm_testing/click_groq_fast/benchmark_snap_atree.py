import time
import os
import json
import base64
import requests
import math
from PIL import ImageGrab
from io import BytesIO
import sys
from dotenv import load_dotenv

load_dotenv()

# Add atree to path
sys.path.append("/Users/harshit/Desktop/YC/atree")
from core import snapshot, axdiff

INTERACTIVE = {"button", "textfield", "textarea", "searchfield", "combobox", "checkbox",
               "menuitem", "tab", "link", "slider", "popupbutton", "cell", "radiobutton"}

def benchmark_snap_atree(target_desc):
    overall_start = time.time()
    
    # 1. Capture Image
    print("Capturing screen...")
    t0 = time.time()
    raw_img = ImageGrab.grab().convert("RGB")
    width, height = raw_img.size
    
    # Sending full resolution
    scale_x = 1.0
    scale_y = 1.0
    
    buffered = BytesIO()
    raw_img.save(buffered, format="JPEG", quality=85)
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    print(f"Screenshot + encode: {time.time()-t0:.3f}s")
    
    # 2. Call Groq
    print("Querying Groq VLM for raw coordinates...")
    t0 = time.time()
    api_key = os.environ.get("GROQ_API_KEY")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    context = "You are a highly precise UI executor for macOS. Analyze the provided screenshot."
    prompt_str = f"{context} Find the '{target_desc}'. If the target is NOT clearly visible on the screen, you MUST set 'status' to 'failed'. If it is visible, output ONLY a valid JSON object with keys 'x' and 'y' representing absolute pixel coordinates relative to the top-left of this image, and 'status' set to 'done'."
    
    payload = {
        "model": "qwen/qwen3.8-27b",
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt_str}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}],
        "temperature": 0.0,
        "max_completion_tokens": 50,
        "response_format": {"type": "json_object"}
    }
    
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print(f"Groq API Error: {resp.text}")
        return
        
    res_json = resp.json()
    content = res_json["choices"][0]["message"]["content"]
    print(f"Groq Latency: {time.time()-t0:.3f}s | Output: {content.strip()}")
    
    parsed = json.loads(content)
    
    # Qwen outputs coordinates normalized to [0, 1000] in the format [ymin, xmin, ymax, xmax]
    if "bbox_2d" in parsed or "box_2d" in parsed:
        box = parsed.get("bbox_2d") or parsed.get("box_2d")
        if len(box) == 4:
            # Format is [ymin, xmin, ymax, xmax]
            ymin, xmin, ymax, xmax = box
            model_x = (xmin + xmax) / 2.0
            model_y = (ymin + ymax) / 2.0
        else:
            model_x, model_y = box[0], box[1]
    elif "x" in parsed and "y" in parsed:
        model_x, model_y = parsed["x"], parsed["y"]
    else:
        print("Model failed to find target.")
        return
        
    # Convert Qwen [0, 1000] scale back to Retina pixel size
    retina_x = (model_x / 1000.0) * raw_img.size[0]
    retina_y = (model_y / 1000.0) * raw_img.size[1]
    
    # ATree uses logical pixels, which are half the size of retina pixels on Macs
    abs_x = retina_x / 2.0
    abs_y = retina_y / 2.0
    
    # 3. ATree Semantic Snapping
    print("Snapshotting ATree and snapping...")
    t0 = time.time()
    env = snapshot.capture() # active app
    tree = env.get("data", {}).get("tree", env)
    _, sidecar = axdiff.flatten(tree)
    
    closest_node = None
    min_dist = float('inf')
    
    for path, meta in sidecar.items():
        bounds = meta.get("bounds")
        if bounds:
            bx, by, bw, bh = bounds["x"], bounds["y"], bounds["width"], bounds["height"]
            center_x = bx + (bw / 2)
            center_y = by + (bh / 2)
            dist = math.hypot(abs_x - center_x, abs_y - center_y)
            if dist < min_dist:
                min_dist = dist
                closest_node = {"path": path, "bounds": bounds, "dist": dist}
                
    print(f"ATree Snap Latency: {time.time()-t0:.3f}s")
    
    if closest_node:
        print(f"✅ Snapped to closest element (dist {closest_node['dist']:.1f}px):")
        print(f"   Bounds: {closest_node['bounds']}")
    else:
        print("No elements with bounds found in ATree.")
        
    print(f"Total Pipeline Latency: {time.time()-overall_start:.3f}s")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "Apple menu icon (top left)"
    benchmark_snap_atree(target)
