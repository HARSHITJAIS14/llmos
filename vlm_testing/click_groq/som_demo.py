import os
import time
import base64
import requests
import json
from PIL import ImageGrab, ImageDraw, ImageFont
from io import BytesIO

def run_som_demo():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("ERROR: Set GROQ_API_KEY environment variable.")
        return

    # 1. Capture Screenshot
    print("Capturing screenshot...")
    raw_img = ImageGrab.grab().convert("RGB")
    
    # 2. Simulate Axtree Data (Drawing 'Set of Mark' bounding boxes)
    # We draw 3 boxes simulating clickable elements (e.g., from an Accessibility Tree)
    draw = ImageDraw.Draw(raw_img)
    
    # Define 3 dummy interactive elements: [x0, y0, x1, y1]
    elements = {
        "1": [100, 100, 300, 200],  # Top left area
        "2": [raw_img.width - 400, 50, raw_img.width - 100, 150], # Top right (e.g. Wi-Fi/Battery)
        "3": [raw_img.width//2 - 200, raw_img.height//2 - 100, raw_img.width//2 + 200, raw_img.height//2 + 100] # Center
    }
    
    try:
        font = ImageFont.truetype("Arial.ttf", 60)
    except:
        font = ImageFont.load_default()

    for el_id, coords in elements.items():
        # Draw red bounding box
        draw.rectangle(coords, outline="red", width=10)
        # Draw ID badge
        draw.rectangle([coords[0], coords[1], coords[0]+80, coords[1]+80], fill="red")
        draw.text((coords[0]+20, coords[1]+10), el_id, fill="white", font=font)

    # Downscale for API speed
    raw_img.thumbnail((1024, 1024))
    
    # Save the overlay image locally so the user can see it!
    overlay_path = "som_overlay_test.jpg"
    raw_img.save(overlay_path, format="JPEG", quality=85)
    print(f"Saved Set-of-Mark image to {overlay_path} - Open this to see what the VLM sees!")

    # Encode to base64
    buffered = BytesIO()
    raw_img.save(buffered, format="JPEG", quality=85)
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    # 3. Call Groq
    model_id = "qwen/qwen3.8-27b"
    context = "You are a UI executor. The image has numbered red boxes over interactive elements."
    task = "Click the element in the top right corner. Output ONLY a valid JSON object with the key 'id' containing the number of the box, and 'status' (done/failed)."
    
    print(f"\n--- Task: {task} ---")
    
    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{context} {task}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]
            }
        ],
        "temperature": 0.0,
        "max_completion_tokens": 50,
        "response_format": {"type": "json_object"}
    }
    
    print("Firing request to Groq...")
    start_time = time.time()
    
    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", 
                               headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, 
                               json=payload)
        
        if response.status_code == 200:
            res_json = response.json()
            content = res_json["choices"][0]["message"]["content"]
            print(f"Total Latency: {time.time() - start_time:.3f} seconds")
            print(f"Output: {content.strip()}")
            
            # 4. Map back to exact pixel-perfect coordinates
            parsed = json.loads(content)
            selected_id = str(parsed.get("id"))
            if selected_id in elements:
                exact_coords = elements[selected_id]
                center_x = (exact_coords[0] + exact_coords[2]) // 2
                center_y = (exact_coords[1] + exact_coords[3]) // 2
                print(f"\n✅ Pixel-Perfect Success! Mapped ID {selected_id} back to exact 4K center coordinates: X={center_x}, Y={center_y}")
        else:
            print(f"API Error: {response.text}")
    except Exception as e:
        print(f"Request failed: {str(e)}")

if __name__ == "__main__":
    run_som_demo()
