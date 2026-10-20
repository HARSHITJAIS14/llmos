import time
import os
import sys
from PIL import ImageGrab

# 1. Setup explicit logging first
LOG_FILE = "api_benchmark.log"
with open(LOG_FILE, "w") as f:
    f.write("--- Starting API Fast-Loop Benchmark ---\n")

def log(msg):
    print(msg, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")
        f.flush()

try:
    from google import genai
    from google.genai import types
except ImportError:
    log("google-genai not installed. Installing now...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-genai"])
    from google import genai
    from google.genai import types

def run_api_benchmark():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log("ERROR: GEMINI_API_KEY environment variable not set.")
        return

    log("Initializing Gemini Client...")
    client = genai.Client(api_key=api_key)
    
    log("Capturing 512x512 screenshot...")
    raw_img = ImageGrab.grab().convert("RGB")
    raw_img.thumbnail((512, 512))
    img_path = "api_test_screenshot.jpg"
    raw_img.save(img_path, format="JPEG", quality=85)
    log(f"Saved screenshot to {img_path}")

    # Use the fastest/smallest model available to avoid queues and maximize TTFT speed
    model_id = "gemini-flash-lite-latest"
    
    context = "You are a fast UI executor."
    task = "Find the Apple menu icon (top left). Output ONLY a valid JSON object with keys 'x' and 'y' representing coordinates to click, and 'status' (done/failed). No markdown blocks."
    prompt = f"{context} {task}"
    
    log(f"Preparing to call {model_id} via official SDK...")
    
    # Uploading the image is handled seamlessly by the SDK
    start_time = time.time()
    
    try:
        # We can pass PIL Image directly to the SDK
        response = client.models.generate_content(
            model=model_id,
            contents=[raw_img, prompt],
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=50,
                response_mime_type="application/json"
            )
        )
        end_time = time.time()
        total_time = end_time - start_time
        
        log(f"\n--- API Request Success ---")
        log(f"Total API Latency (Network + TTFT + Generation): {total_time:.3f} seconds")
        log(f"Raw Output: {response.text.strip()}")
        
    except Exception as e:
        end_time = time.time()
        log(f"\n--- API Request Failed ---")
        log(f"Failed after {end_time - start_time:.3f} seconds.")
        log(f"Error: {str(e)}")
        # Fallback to gemini-1.5-flash if 2.5 is not available in this region/key yet
        log("Retrying with gemini-1.5-flash...")
        try:
            start_time = time.time()
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=[raw_img, prompt],
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=50,
                    response_mime_type="application/json"
                )
            )
            end_time = time.time()
            log(f"Retry Success! Latency: {end_time - start_time:.3f} seconds")
            log(f"Raw Output: {response.text.strip()}")
        except Exception as e2:
            log(f"Retry failed: {str(e2)}")

if __name__ == "__main__":
    run_api_benchmark()
