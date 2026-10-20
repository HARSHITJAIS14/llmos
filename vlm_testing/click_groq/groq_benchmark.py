import time
import os
import sys
import base64
import requests
import datetime
from PIL import ImageGrab
from io import BytesIO

# Generate a unique timestamped log file for every run
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = f"logs/groq_benchmark_{timestamp}.log"
with open(LOG_FILE, "w") as f:
    f.write(f"--- Starting Groq LPU Fast-Loop Benchmark at {timestamp} ---\n")

def log(msg):
    print(msg, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")
        f.flush()

def run_groq_benchmark():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        log("ERROR: GROQ_API_KEY environment variable not set.")
        log("Run: export GROQ_API_KEY='your_key' and try again.")
        return

    log("Capturing 1024x1024 high-quality screenshot...")
    raw_img = ImageGrab.grab().convert("RGB")
    raw_img.thumbnail((1024, 1024))
    
    buffered = BytesIO()
    raw_img.save(buffered, format="JPEG", quality=85)
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    # We use Qwen3.8-27B which is the currently active multimodal model on Groq
    model_id = "qwen/qwen3.8-27b"
    
    # Accept custom CUA task from command line arguments
    context = "You are a fast UI executor for macOS. Analyze the provided screenshot."
    if len(sys.argv) > 1:
        task = sys.argv[1]
    else:
        task = "Find the Apple menu icon (top left)."
        
    log(f"--- Task: {task} ---")
    prompt_str = f"{context} {task} Output ONLY a valid JSON object with keys 'x' and 'y' representing absolute pixel coordinates to click, and 'status' (done/failed)."
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_id,
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
    
    log(f"Firing request to Groq LPU API ({model_id})...")
    start_time = time.time()
    
    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        end_time = time.time()
        
        if response.status_code == 200:
            res_json = response.json()
            content = res_json["choices"][0]["message"]["content"]
            log(f"\n--- API Request Success ---")
            log(f"Total Groq Latency: {end_time - start_time:.3f} seconds")
            log(f"Output: {content.strip()}")
        else:
            log(f"API Error: {response.status_code} - {response.text}")
    except Exception as e:
        log(f"Request failed: {str(e)}")

if __name__ == "__main__":
    run_groq_benchmark()
