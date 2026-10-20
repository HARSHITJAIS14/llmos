import os
import sys
import time
import base64
import subprocess
from dotenv import load_dotenv

# Load Lightcone API key from the parent folder's .env
load_dotenv("../click_groq_fast/.env")

# The .env variable the user created is Lightcone_API_KEY, but the SDK expects TZAFON_API_KEY
if "TZAFON_API_KEY" not in os.environ and "Lightcone_API_KEY" in os.environ:
    os.environ["TZAFON_API_KEY"] = os.environ["Lightcone_API_KEY"]

try:
    from tzafon import Lightcone
except ImportError:
    print("Please run: pip install tzafon")
    sys.exit(1)

def take_screenshot(out_path):
    print("Capturing desktop screenshot...")
    t0 = time.time()
    subprocess.run(["screencapture", "-x", "-t", "png", out_path])
    t1 = time.time()
    print(f"Screenshot Latency: {t1 - t0:.3f}s")
    
    with open(out_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

def benchmark_northstar():
    client = Lightcone()
    
    img_path = "test_screenshot.png"
    b64_image = take_screenshot(img_path)
    
    data_url = f"data:image/png;base64,{b64_image}"
    
    TOOL = {
        "type": "computer_use", 
        "display_width": 1440, 
        "display_height": 900, 
        "environment": "desktop"
    }
    
    TASK = "Click on the 'Aarzu' video thumbnail or label."
    
    print("Firing request to Lightcone (tzafon.northstar-cua-fast)...")
    t0 = time.time()
    
    try:
        response = client.responses.create(
            model="tzafon.northstar-cua-fast",
            tools=[TOOL],
            input=[{"role": "user", "content": [
                {"type": "input_text", "text": TASK},
                {"type": "input_image", "image_url": data_url, "detail": "auto"},
            ]}],
        )
        t1 = time.time()
        print(f"Northstar Latency: {t1 - t0:.3f}s")
        
        for out in response.output or []:
            if out.type == "computer_call":
                action = out.action
                print(f"Northstar Action: {action.type} -> {action}")
                
    except Exception as e:
        print(f"API Error: {e}")

if __name__ == "__main__":
    overall_t0 = time.time()
    benchmark_northstar()
    print(f"Total Pipeline Latency: {time.time() - overall_t0:.3f}s")
