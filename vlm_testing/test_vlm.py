import time
import json
from PIL import ImageGrab
import sys
import subprocess

try:
    from mlx_vlm import load, generate
    from mlx_vlm.utils import load_config
    import jinja2
except ImportError:
    print("Dependencies missing. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mlx-vlm", "Pillow", "pyautogui", "jinja2"])
    from mlx_vlm import load, generate
    from mlx_vlm.utils import load_config

# model
model_path = "Tzafon/Northstar-CUA-Fast"
print(f"Loading {model_path} with strict=False...")
start_load = time.time()
model, processor = load(model_path, strict=False)
config = load_config(model_path)
print(f"Model loaded in {time.time() - start_load:.2f} seconds")

# capture
print("Capturing screenshot...")
img = ImageGrab.grab()
img = img.convert("RGB")
img.thumbnail((1024, 1024))
img_path = "test_screenshot.jpg"
img.save(img_path)

# prompt
context = "You are a fast UI executor."
task = "Find the Apple menu icon (top left)."
prompt = f"{context} {task} Output ONLY a valid JSON object with keys \"x\" and \"y\" representing the coordinates to click, and \"status\" (done/failed). No other text."
messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
formatted_prompt = processor.apply_chat_template(messages, add_generation_prompt=True)

# generate
print("Running inference...")
start_inf = time.time()
output = generate(model, processor, formatted_prompt, [img_path], verbose=False, max_tokens=50)
end_inf = time.time()

print("\n--- Results ---")
print(f"Inference Time: {end_inf - start_inf:.4f} seconds")
print(f"Raw Output:\n{output}")
