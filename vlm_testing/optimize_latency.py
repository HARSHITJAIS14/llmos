import time
import json
import sys
from PIL import ImageGrab
import mlx.core as mx
from mlx_vlm import load, generate
from mlx_vlm.utils import load_config

# Setup a dedicated log file
LOG_FILE = "benchmark.log"
with open(LOG_FILE, "w") as f:
    f.write("--- Starting VLM Benchmark ---\n")

def log(msg):
    # Print to console and flush so it shows up in tail instantly
    print(msg, flush=True)
    # Write to local file and flush
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")
        f.flush()

def run_benchmark():
    log("Initializing script...")
    
    # 1. Load Model
    model_path = "Tzafon/Northstar-CUA-Fast"
    log(f"Loading {model_path} with strict=False...")
    start_load = time.time()
    model, processor = load(model_path, strict=False)
    log(f"Model loaded in {time.time() - start_load:.2f} seconds.")
    
    # 2. Capture a single screenshot to reuse
    log("Capturing baseline screenshot...")
    raw_img = ImageGrab.grab().convert("RGB")
    log(f"Screenshot captured at size: {raw_img.size}")
    
    context = "You are a fast UI executor."
    task = "Find the Apple menu icon (top left)."
    prompt = f"{context} {task} Output ONLY a valid JSON object with keys \"x\" and \"y\" representing the coordinates to click, and \"status\" (done/failed). No other text."
    
    resolutions = [1024, 768, 512, 384]
    results = []
    
    # WARM UP RUN
    log("\n--- Running Warm Up (JIT Compile) ---")
    img_warm = raw_img.copy()
    img_warm.thumbnail((256, 256))
    img_warm.save("warmup.jpg")
    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
    fmt_prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
    log("Executing warm up inference (this compiles the GPU shaders)...")
    _ = generate(model, processor, fmt_prompt, ["warmup.jpg"], verbose=False, max_tokens=10)
    log("Warm up complete. Shaders cached.")
    
    for res in resolutions:
        log(f"\n--- Benchmarking Resolution: {res}x{res} ---")
        img_test = raw_img.copy()
        img_test.thumbnail((res, res))
        test_path = f"test_{res}.jpg"
        img_test.save(test_path)
        log(f"Saved downscaled image to {test_path} (Size: {img_test.size})")
        
        messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
        fmt_prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
        
        # mx.clear_cache() handles memory cleanup without triggering recompilation
        mx.clear_cache()
        
        log(f"Starting inference timer for {res}x{res}...")
        start_time = time.time()
        output = generate(model, processor, fmt_prompt, [test_path], verbose=False, max_tokens=50)
        end_time = time.time()
        total_time = end_time - start_time
        
        out_str = output.text if hasattr(output, 'text') else str(output)
        log(f"Raw Generation Output: {out_str}")
        
        # Parsing JSON
        try:
            parsed = json.loads(out_str.strip().strip("```json").strip("```"))
            valid_json = True
            log(f"Successfully parsed JSON: {parsed}")
        except Exception as e:
            parsed = {}
            valid_json = False
            log(f"Failed to parse JSON. Error: {e}")
            
        log(f"Total time for {res}x{res}: {total_time:.3f} seconds.")
        
        results.append({
            "resolution": res,
            "total_time": total_time,
            "valid_json": valid_json,
            "parsed": parsed
        })
        
    log("\n--- Final Summary ---")
    for r in results:
        log(f"Res: {r['resolution']:<4} | Time: {r['total_time']:.3f}s | Output: {r['parsed']}")

if __name__ == "__main__":
    run_benchmark()
