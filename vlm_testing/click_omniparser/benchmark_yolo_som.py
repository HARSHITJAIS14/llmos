import os
import sys
import time
import json
import base64
import requests
import torch
from io import BytesIO
from PIL import ImageGrab, Image, ImageDraw, ImageFont
from dotenv import load_dotenv

# Path setup for OmniParser
sys.path.append(os.path.join(os.path.dirname(__file__), 'OmniParser'))
os.chdir(os.path.join(os.path.dirname(__file__), 'OmniParser'))

from util.utils import get_yolo_model, predict_yolo

load_dotenv(os.path.join(os.path.dirname(__file__), "../click_groq_fast/.env"))

def encode_image(img):
    buffered = BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def benchmark_yolo_som(target_desc):
    overall_start = time.time()
    
    print("Capturing screen...")
    t0 = time.time()
    raw_img = ImageGrab.grab().convert("RGB")
    raw_img.thumbnail((1500, 1500))
    print(f"Screenshot taken: {time.time()-t0:.3f}s")
    
    print("Loading YOLO Model...")
    t0 = time.time()
    yolo_model = get_yolo_model('weights/icon_detect_v3/model.pt')
    print(f"YOLO Load Latency: {time.time()-t0:.3f}s")
    
    print("Running YOLO inference and drawing Set of Mark (SoM)...")
    t0 = time.time()
    
    # Run YOLO using OmniParser's wrapper
    boxes, _, _ = predict_yolo(model=yolo_model, image=raw_img, box_threshold=0.05, imgsz=(raw_img.size[1], raw_img.size[0]), scale_img=False, iou_threshold=0.1)
    
    # Normalize back to pixel space
    if isinstance(boxes, torch.Tensor):
        boxes = boxes.cpu().numpy()
    
    # Draw boxes and IDs
    annotated_img = raw_img.copy()
    draw = ImageDraw.Draw(annotated_img)
    label_coordinates = {}
    
    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = box
        draw.rectangle([x1, y1, x2, y2], outline="red", width=2)
        # Draw ID background and text
        text = str(i)
        draw.rectangle([x1, y1, x1+20, y1+15], fill="red")
        draw.text((x1+2, y1), text, fill="white")
        
        # Save center coords
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        label_coordinates[i] = (cx / raw_img.size[0], cy / raw_img.size[1]) # Ratio
        
    print(f"YOLO + Drawing Latency: {time.time()-t0:.3f}s")
    
    img_b64 = encode_image(annotated_img)
    annotated_img.save("som_overlay_debug.jpg")
    
    print(f"Querying Groq VLM with {len(label_coordinates)} SoM IDs...")
    t0 = time.time()
    
    api_key = os.environ.get("GROQ_API_KEY")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    context = "You are a fast UI executor for macOS. Analyze the provided screenshot which has numbered bounding boxes drawn over UI elements."
    prompt_str = f"{context} Find the '{target_desc}'. Output ONLY a valid JSON object with the key 'id' containing the integer ID of the box, and 'status' (done/failed). Do NOT output anything else."
    
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
    
    try:
        parsed = json.loads(content)
        if parsed.get("status") == "done":
            box_id = int(parsed.get("id", -1))
            if box_id in label_coordinates:
                print(f"✅ Success! Target found at Box ID {box_id}. Coords (ratio): {label_coordinates[box_id]}")
            else:
                print(f"❌ Box ID {box_id} not found in label_coordinates.")
        else:
            print("❌ VLM failed to find the target.")
    except Exception as e:
        print(f"Error parsing JSON: {e}")

    print(f"Total YOLO + VLM Pipeline Latency: {time.time()-overall_start:.3f}s")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "Apple menu icon (top left)"
    benchmark_yolo_som(target)
