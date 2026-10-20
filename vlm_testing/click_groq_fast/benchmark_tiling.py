import time
import os
import json
import base64
import requests
import concurrent.futures
from PIL import ImageGrab
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

def encode_image(img):
    buffered = BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def call_groq(quadrant_name, img_b64, target_desc, offset_x, offset_y):
    api_key = os.environ.get("GROQ_API_KEY")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    context = "You are a fast UI executor for macOS. Analyze the provided screenshot."
    prompt_str = f"{context} Find the '{target_desc}'. Output ONLY a valid JSON object with keys 'x' and 'y' representing absolute pixel coordinates relative to the top-left of this image, and 'status' (done/failed)."
    
    payload = {
        "model": "qwen/qwen3.8-27b",
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
    
    start_time = time.time()
    try:
        response = requests.post(url, headers=headers, json=payload)
        latency = time.time() - start_time
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            return {"quadrant": quadrant_name, "latency": latency, "result": content, "offset": (offset_x, offset_y), "error": None}
        else:
            return {"quadrant": quadrant_name, "latency": latency, "result": None, "offset": (offset_x, offset_y), "error": response.text}
    except Exception as e:
        return {"quadrant": quadrant_name, "latency": time.time() - start_time, "result": None, "offset": (offset_x, offset_y), "error": str(e)}

def test_tiling():
    target_desc = "Apple menu icon (top left)"
    
    print("Capturing full screen...")
    raw_img = ImageGrab.grab().convert("RGB")
    width, height = raw_img.size
    print(f"Original size: {width}x{height}")
    
    # Calculate quadrant boundaries
    mid_x, mid_y = width // 2, height // 2
    
    quadrants = {
        "Top-Left": (0, 0, mid_x, mid_y),
        "Top-Right": (mid_x, 0, width, mid_y),
        "Bottom-Left": (0, mid_y, mid_x, height),
        "Bottom-Right": (mid_x, mid_y, width, height)
    }
    
    tasks = []
    print("Cropping and downscaling quadrants to 1024x1024...")
    for name, box in quadrants.items():
        crop = raw_img.crop(box)
        # Downscale to 1024x1024 as requested
        crop.thumbnail((1024, 1024))
        b64 = encode_image(crop)
        tasks.append((name, b64, target_desc, box[0], box[1]))
        
    print("Firing 4 parallel API requests to Groq...")
    start_total = time.time()
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(call_groq, name, b64, target_desc, off_x, off_y) for name, b64, target_desc, off_x, off_y in tasks]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
            
    total_time = time.time() - start_total
    print(f"\n--- TILING RESULTS (Total Latency: {total_time:.3f}s) ---")
    
    for res in results:
        print(f"[{res['quadrant']}] Latency: {res['latency']:.3f}s")
        if res['error']:
            print(f"  Error: {res['error']}")
        else:
            print(f"  Output: {res['result'].strip()}")

if __name__ == "__main__":
    test_tiling()
